"""Execute the supported SCL subset for PLC scan regression checks.
NOT a Siemens compiler/emulator: no CPU typing, overflow, PN transport or safety validation.
Run: python -m unittest discover -s tests -v
"""
from pathlib import Path
import re

V20 = Path(__file__).resolve().parents[1] / 'plc' / 'v20'


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
    def __init__(self, block_name):
        source = (V20 / (block_name + '.scl')).read_text()
        declarations, body = source.split('\nBEGIN\n', 1)
        self.code = Parser(tokens(body.split('END_FUNCTION_BLOCK')[0])).block()
        self.v = {}
        for name, typ, default in re.findall(r'^\s+(\w+)\s*:\s*(\w+)(?:\s*:=\s*([^;]+))?;', declarations, re.M):
            if typ == 'TON_TIME': value = Timer()
            elif typ == 'R_TRIG': value = Edge()
            elif default: value = self.evaluate(tokens(default))
            else: value = False if typ == 'Bool' else 0
            self.v[name] = value

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
        return self.v
