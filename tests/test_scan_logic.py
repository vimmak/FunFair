"""Execute this FB's supported SCL subset for regression checks.
NOT a Siemens compiler/emulator: no CPU typing, overflow, PN transport or safety validation.
Run: python -m unittest discover -s tests -v
"""
from pathlib import Path
import re
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'plc/FB_FunFair_StopGame.scl'


def tokens(text):
    text = re.sub(r'//[^\n]*', '', text)
    pattern = r'W#16#[0-9A-Fa-f]+|T#\d+(?:ms|s)|#[A-Za-z_]\w*(?:\.\w+)?|:=|<>|<=|>=|\d+(?:\.\d+)?|[A-Za-z_]\w*|[();:,=<>+*/\-]'
    result = re.findall(pattern, text)
    if re.sub(pattern, '', text).strip():
        raise ValueError('Unsupported syntax in simulator')
    return result


class Parser:
    def __init__(self, ts):
        self.ts, self.i = ts, 0

    def pop(self, expected=None):
        t = self.ts[self.i]
        self.i += 1
        if expected is not None and t != expected:
            raise ValueError((expected, t))
        return t

    def expr(self, stop):
        out, depth = [], 0
        while self.i < len(self.ts):
            t = self.ts[self.i]
            if depth == 0 and t in stop:
                break
            depth += (t == '(') - (t == ')')
            out.append(self.pop())
        return out

    def block(self, stop=(), case=False):
        out = []
        while self.i < len(self.ts) and self.ts[self.i] not in stop:
            if case and self.ts[self.i].isdigit() and self.ts[self.i+1] == ':':
                break
            t = self.pop()
            if t == 'IF':
                branches = []
                while True:
                    expr = self.expr({'THEN'})
                    self.pop('THEN')
                    branches.append((expr, self.block({'ELSIF', 'ELSE', 'END_IF'})))
                    if self.ts[self.i] != 'ELSIF':
                        break
                    self.pop()
                other = []
                if self.ts[self.i] == 'ELSE':
                    self.pop()
                    other = self.block({'END_IF'})
                self.pop('END_IF'); self.pop(';')
                out.append(('if', branches, other))
            elif t == 'CASE':
                expr = self.expr({'OF'}); self.pop('OF')
                branches = {}
                while self.ts[self.i] not in ('ELSE', 'END_CASE'):
                    key = int(self.pop()); self.pop(':')
                    branches[key] = self.block({'ELSE', 'END_CASE'}, case=True)
                other = []
                if self.ts[self.i] == 'ELSE':
                    self.pop(); other = self.block({'END_CASE'})
                self.pop('END_CASE'); self.pop(';')
                out.append(('case', expr, branches, other))
            elif t.startswith('#'):
                if self.ts[self.i] == ':=':
                    self.pop(); expr = self.expr({';'}); self.pop(';')
                    out.append(('assign', t[1:], expr))
                else:
                    self.pop('('); args = {}
                    while self.ts[self.i] != ')':
                        key = self.pop(); self.pop(':=')
                        args[key] = self.expr({',', ')'})
                        if self.ts[self.i] == ',': self.pop()
                    self.pop(')'); self.pop(';')
                    out.append(('call', t[1:], args))
            else:
                raise ValueError(('Unsupported statement', t))
        return out


class Timer:
    def __init__(self):
        self.Q, self.elapsed, self.active = False, 0, False

    def call(self, dt, IN, PT):
        if not IN:
            self.elapsed, self.active = 0, False
        elif self.active:
            self.elapsed += dt
        else:
            self.active = True
        self.Q = bool(IN and self.elapsed >= PT)
        self.ET = min(self.elapsed, PT)


class Edge:
    def __init__(self): self.Q, self.previous = False, False
    def call(self, dt, CLK):
        self.Q = bool(CLK and not self.previous)
        self.previous = CLK


class ScanModel:
    def __init__(self):
        source = SOURCE.read_text()
        declarations, body = source.split('\nBEGIN\n', 1)
        self.code = Parser(tokens(body.split('END_FUNCTION_BLOCK')[0])).block()
        self.v = {}
        for name, typ, default in re.findall(r'^\s+(\w+)\s*:\s*(\w+)(?:\s*:=\s*([^;]+))?;', declarations, re.M):
            if typ == 'TON_TIME': value = Timer()
            elif typ == 'R_TRIG': value = Edge()
            elif default: value = self.evaluate(tokens(default))
            else: value = False if typ == 'Bool' else 0
            self.v[name] = value
        self.v.update(Enable=True, Commissioned=True, MotionPermit=True,
            DataValid=True, Ready=True, FieldbusControl=True, ButtonReleased=True,
            LowPosition_um=10000, HighPosition_um=50000, TargetPosition_um=30000,
            Tolerance_um=1000, Velocity_um_s=10000, VerifiedMin_um=0,
            VerifiedMax_um=60000, VerifiedMinVelocity_um_s=1000,
            VerifiedMaxVelocity_um_s=100000, ActualPosition_um=30000)

    def evaluate(self, expr):
        out = []
        for t in expr:
            if t.startswith('#'):
                root, *attr = t[1:].split('.')
                out.append(f'v[{root!r}]' + ('.'+attr[0] if attr else ''))
            elif t.startswith('T#'):
                m = re.fullmatch(r'T#(\d+)(ms|s)', t)
                out.append(str(int(m[1]) * (1000 if m[2]=='s' else 1)))
            elif t.startswith('W#16#'): out.append(str(int(t[5:],16)))
            else: out.append({'AND':'and','OR':'or','NOT':'not','TRUE':'True',
                'FALSE':'False','=':'==','<>':'!=','ABS':'abs',
                'DINT_TO_LREAL':'float','LREAL_TO_DINT':'round',
                'DINT_TO_TIME':'int','TIME_TO_DINT':'int','MOD':'%'}.get(t,t))
        return eval(' '.join(out), {'__builtins__':{},'abs':abs,'float':float,'round':round,'int':int}, {'v':self.v})

    def run(self, code, dt):
        for stmt in code:
            kind = stmt[0]
            if kind == 'assign': self.v[stmt[1]] = self.evaluate(stmt[2])
            elif kind == 'call':
                self.v[stmt[1]].call(dt, **{k:self.evaluate(e) for k,e in stmt[2].items()})
            elif kind == 'if':
                for expr, branch in stmt[1]:
                    if self.evaluate(expr):
                        self.run(branch,dt); break
                else: self.run(stmt[2],dt)
            elif kind == 'case':
                self.run(stmt[2].get(self.evaluate(stmt[1]),stmt[3]),dt)

    def scan(self, n=1, **inputs):
        self.v.update(inputs)
        for _ in range(n):
            self.run(self.code, 5)
            assert not (self.v['MoveAbsolute'] and self.v['ControlledStop'])
        return self.v

    def start(self):
        self.scan(FirstScan=True)
        self.scan(20,FirstScan=False)
        assert self.v['State']==40
        self.scan(ReceivedToggle=True)
        assert self.v['State']==50

    def click(self):
        self.scan(6,ButtonReleased=False)
        self.scan(3,ButtonReleased=True)

    def finish_stop(self):
        self.scan(ReceivedToggle=not self.v['ReceivedToggle'],
                  CommandDone=True,PositionReached=True)
        self.scan(45)
        assert self.v['State']==80


class GameTests(unittest.TestCase):
    def test_auto_run_and_hold_does_not_stop(self):
        m=ScanModel(); m.start()
        m.scan(30,ButtonReleased=False)
        self.assertEqual(m.v['State'],50)
        m.scan(3,ButtonReleased=True)
        self.assertEqual(m.v['State'],60)

    def test_full_click_stop_score_then_click_resume(self):
        m=ScanModel(); m.start(); m.click(); m.finish_stop()
        self.assertTrue(m.v['ResultValid']); self.assertTrue(m.v['Success'])
        m.scan(20); self.assertEqual(m.v['State'],80)
        m.click(); self.assertEqual(m.v['State'],30)
        self.assertFalse(m.v['ResultValid'])

    def test_initial_held_button_requires_release(self):
        m=ScanModel(); m.scan(FirstScan=True,ButtonReleased=False)
        m.scan(30,FirstScan=False); self.assertEqual(m.v['State'],10)
        m.scan(20,ButtonReleased=True)
        self.assertEqual(m.v['State'],40)
        self.assertFalse(m.v['ControlledStop'])

    def test_bounce_does_not_count_as_click(self):
        m=ScanModel(); m.start()
        for _ in range(5):
            m.scan(ButtonReleased=False); m.scan(ButtonReleased=True)
        self.assertEqual(m.v['State'],50)

    def test_late_move_ack_not_used_as_stop_ack(self):
        m=ScanModel(); m.scan(FirstScan=True); m.scan(20,FirstScan=False)
        m.click(); self.assertEqual(m.v['State'],55)
        m.scan(ReceivedToggle=True)
        self.assertEqual(m.v['State'],60); self.assertFalse(m.v['StopAcked'])
        m.scan(5); self.assertEqual(m.v['State'],60)
        m.scan(ReceivedToggle=False)
        self.assertEqual(m.v['State'],70)

    def test_click_during_stop_is_not_queued(self):
        m=ScanModel(); m.start(); m.click(); m.click(); m.finish_stop()
        m.scan(20); self.assertEqual(m.v['State'],80)

    def test_press_started_during_stop_cannot_resume_on_release(self):
        m=ScanModel(); m.start(); m.click()
        m.scan(6,ButtonReleased=False); m.finish_stop()
        m.scan(4,ButtonReleased=True); self.assertEqual(m.v['State'],80)
        m.click(); self.assertEqual(m.v['State'],30)

    def test_stop_has_priority_over_endpoint_reverse(self):
        m=ScanModel(); m.start(); m.scan(6,ButtonReleased=False)
        m.scan(ButtonReleased=True)
        m.scan(2,ActualPosition_um=50000,CommandDone=True,PositionReached=True)
        self.assertIn(m.v['State'],(55,60))
        self.assertFalse(m.v['MoveAbsolute'])

    def test_strict_tolerance_boundary(self):
        m=ScanModel(); m.start(); m.click()
        m.scan(ActualPosition_um=31000); m.finish_stop()
        self.assertTrue(m.v['ResultValid']); self.assertFalse(m.v['Success'])

    def test_drift_and_timeout_do_not_score(self):
        m=ScanModel(); m.start(); m.click()
        m.scan(ReceivedToggle=False,CommandDone=True,PositionReached=True)
        for _ in range(650):
            m.scan(ActualPosition_um=m.v['ActualPosition_um']+1)
        self.assertEqual(m.v['State'],900); self.assertFalse(m.v['ResultValid'])

    def test_data_loss_does_not_auto_resume(self):
        m=ScanModel(); m.start(); m.scan(DataValid=False)
        self.assertEqual(m.v['State'],900)
        m.scan(10,DataValid=True); self.assertEqual(m.v['State'],900)
        m.scan(6,ResetButton=True); self.assertEqual(m.v['State'],80)
        m.scan(10,ResetButton=False); self.assertEqual(m.v['State'],80)
        m.click(); self.assertEqual(m.v['State'],30)

    def test_permit_restore_requires_explicit_recovery(self):
        m=ScanModel(); m.start(); m.scan(MotionPermit=False)
        self.assertEqual(m.v['State'],900)
        self.assertFalse(m.v['FastStopRelease'])
        m.scan(10,MotionPermit=True); self.assertEqual(m.v['State'],900)
        m.scan(6,ResetButton=True); self.assertEqual(m.v['State'],80)
        m.scan(10,ResetButton=False); self.assertEqual(m.v['State'],80)
        m.click(); self.assertEqual(m.v['State'],30)

    def test_ack_timeout_blocks_motion_and_result(self):
        m=ScanModel(); m.scan(FirstScan=True); m.scan(250,FirstScan=False)
        self.assertEqual(m.v['State'],900)
        self.assertFalse(m.v['MoveAbsolute']); self.assertFalse(m.v['ResultValid'])

    def test_reset_in_motion_aborts_without_score(self):
        m=ScanModel(); m.start(); m.scan(6,ResetButton=True)
        m.scan(ResetButton=False); m.finish_stop()
        self.assertFalse(m.v['ResultValid']); self.assertEqual(m.v['FaultCode'],7)
        m.click(); self.assertEqual(m.v['State'],30)


if __name__=='__main__': unittest.main()
