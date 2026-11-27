"""OB1 scan tests: execute the wrapper and game SCL, substitute the PN device."""
import unittest
from types import SimpleNamespace

from scl_scan import ScanModel


class GameInstance:
    def __init__(self):
        self.fb = ScanModel('FB_StopGameV20')

    def call(self, dt, **inputs):
        self.fb.scan(**inputs)

    def __getattr__(self, name):
        return self.fb.v[name]


class NativePort(SimpleNamespace):
    """Native cyclic FB boundary. Tests supply device feedback explicitly."""
    def call(self, dt, **inputs):
        self.command = inputs
        assert inputs['b_RELEASE_FUNCTION_BLOCK'] and inputs['b_00_FAST_STOP']
        assert sum(inputs[name] for name in ('b_01_STOP', 'b_02_ACKNOLEDGE',
            'b_13_MOVE_TO_ABSOLUTE_POSITION')) <= 1


class AutoGame(unittest.TestCase):
    def setUp(self):
        self.ob = ScanModel('FB_FunFairEGU_V20')
        self.port = NativePort(b_00_READY_FOR_OPERATION=True,
            b_01_CONTOL_AUTHORITY_FIELDBUS=True, b_07_ERROR=False,
            b_03_NOT_FEASIBLE=False, b_04_COMMAND_SUCCESSFULLY_PROCESSED=False,
            b_13_POSITION_REACHED=False, b_05_COMMAND_RECEIVED_TOGGLE=False,
            di_ACTUAL_POSITION=1000, i_DIAGNOSIS_ERROR=0)
        self.v = self.ob.v
        self.v.update(Game=GameInstance(), EGU=self.port, OpenPosition_um=1000,
            ClosePosition_um=23000, TargetPosition_um=13000, Tolerance_um=2000,
            Velocity_um_s=2000, FirstScan=True, MotionPermit=True, DataValid=True,
            InputHW=278, OutputHW=277)
        self.scan()
        self.v['FirstScan'] = False

    def scan(self, n=1, **inputs):
        self.v.update(inputs)
        for _ in range(n):
            self.ob.run(self.ob.code, 5)

    def ack(self):
        self.port.b_05_COMMAND_RECEIVED_TOGGLE ^= True
        self.scan()

    def press_reset(self):
        self.scan(ResetButton=True)
        self.scan(ResetButton=False)

    def lights(self):
        return tuple(self.v[name] for name in ('LampDO0', 'LampDO1', 'LampDO2'))

    def moving(self):
        self.scan(16)
        self.assertTrue(self.port.command['b_13_MOVE_TO_ABSOLUTE_POSITION'])
        self.ack()
        self.assertEqual(self.v['State'], 50)

    def pause_at(self, position):
        self.press_reset()
        self.moving()
        self.scan(PauseDI=True)
        self.assertTrue(self.port.command['b_01_STOP'])
        self.scan(PauseDI=False)
        self.ack()
        self.port.di_ACTUAL_POSITION = position
        self.port.b_04_COMMAND_SUCCESSFULLY_PROCESSED = True
        self.scan(20)
        self.assertFalse(self.v['ResultValid'])
        self.scan(25)
        self.assertTrue(self.v['ResultValid'])

    def test_auto_reverse_and_native_setpoints(self):
        self.press_reset()
        self.moving()
        c = self.port.command
        self.assertEqual((c['di_POSITION'], c['di_VELOCITY']), (23000, 2000))
        self.assertEqual((c['HW_ADDRESS_INPUT'], c['HW_ADDRESS_OUTPUT']), (278, 277))
        for endpoint, following in [(23000, 1000), (1000, 23000)]:
            self.port.di_ACTUAL_POSITION = endpoint
            self.port.b_13_POSITION_REACHED = True
            self.port.b_04_COMMAND_SUCCESSFULLY_PROCESSED = True
            self.scan()
            self.assertFalse(self.port.command['b_13_MOVE_TO_ABSOLUTE_POSITION'])
            self.moving()
            self.assertEqual(self.port.command['di_POSITION'], following)

    def test_boot_held_reset_or_offline_never_moves(self):
        self.scan(20, FirstScan=True, ResetButton=True, DataValid=False)
        self.scan(30, FirstScan=False, DataValid=True)
        self.assertEqual(self.v['State'], 10)
        self.assertEqual(self.lights(), (False, False, False))
        self.scan(20, ResetButton=False)
        self.assertEqual(self.v['State'], 10)
        self.press_reset()
        self.moving()

    def test_pause_press_latches_score_and_reset_resumes(self):
        self.pause_at(11900)
        self.assertEqual((self.v['ActualPosition_um'], self.v['SignedError_um']), (11900, -1100))
        self.assertTrue(self.v['Success'])
        self.scan(30, TargetPosition_um=8000)
        self.assertEqual(self.v['SignedError_um'], -1100)
        self.assertEqual(self.v['State'], 80)
        self.scan(PauseDI=True, ResetButton=True)
        self.scan(PauseDI=False, ResetButton=False)
        self.assertEqual(self.v['State'], 80)
        self.press_reset()
        self.assertFalse(self.port.command['b_02_ACKNOLEDGE'])
        self.assertFalse(self.v['ResultValid'])
        self.assertEqual(self.v['SignedError_um'], 3900)
        self.moving()
        self.assertEqual(self.port.command['di_POSITION'], 23000)
        self.pause_at(8000)
        self.assertTrue(self.v['Success'])

    def test_boundary_misses(self):
        self.pause_at(15000)
        self.assertFalse(self.v['Success'])

    def test_early_reset_waits_for_new_press_after_stop(self):
        self.press_reset()
        self.scan(16)
        self.scan(PauseDI=True)
        self.assertEqual(self.v['State'], 55)
        self.scan(PauseDI=False, ResetButton=True)
        self.ack()
        self.assertEqual(self.v['State'], 60)
        self.assertTrue(self.port.command['b_01_STOP'])
        self.ack()
        self.port.b_04_COMMAND_SUCCESSFULLY_PROCESSED = True
        self.scan(30)
        self.port.di_ACTUAL_POSITION += 50
        self.scan(25)
        self.assertEqual(self.v['State'], 70)
        self.scan(40)
        self.assertEqual(self.v['State'], 80)
        self.scan(20, ResetButton=False)
        self.assertEqual(self.v['State'], 80)
        self.press_reset()
        self.moving()

    def test_pause_during_recovery_prevents_motion_until_new_reset(self):
        self.port.b_07_ERROR = True
        self.press_reset()
        self.scan(PauseDI=True)
        self.scan(PauseDI=False)
        self.port.b_07_ERROR = False
        self.scan(20)
        self.assertEqual(self.v['State'], 10)
        self.press_reset()
        self.moving()

    def test_startup_fault_ack_outlasts_button_and_awaits_ready(self):
        self.port.b_07_ERROR = True
        self.port.i_DIAGNOSIS_ERROR = 0xEF
        self.port.b_03_NOT_FEASIBLE = True
        self.scan()
        self.press_reset()
        self.assertEqual(self.v['State'], 905)
        self.assertTrue(self.port.command['b_02_ACKNOLEDGE'])
        self.port.b_07_ERROR = False
        self.port.i_DIAGNOSIS_ERROR = 0
        self.scan(30)
        self.assertFalse(self.port.command['b_02_ACKNOLEDGE'])
        self.assertEqual(self.v['State'], 905)
        self.assertEqual(self.lights(), (False, False, False))
        self.port.b_03_NOT_FEASIBLE = False
        self.scan()
        self.moving()

    def test_runtime_fault_latches_then_recovers_with_reset(self):
        self.press_reset()
        self.moving()
        self.port.b_07_ERROR = True
        self.port.i_DIAGNOSIS_ERROR = 0xCA
        self.scan()
        self.assertEqual((self.v['FaultCode'], self.v['GripperFaultCode']), (1, 0xCA))
        self.assertEqual(self.lights(), (False, False, False))
        self.press_reset()
        self.assertTrue(self.port.command['b_02_ACKNOLEDGE'])
        self.port.b_07_ERROR = False
        self.port.i_DIAGNOSIS_ERROR = 0
        self.scan()
        self.moving()
        self.assertEqual(self.v['FaultCode'], 0)

    def test_unanswered_ack_can_be_retried(self):
        self.port.b_07_ERROR = True
        self.press_reset()
        self.scan(610)
        self.assertEqual((self.v['State'], self.v['FaultCode']), (900, 10))
        self.assertFalse(self.port.command['b_02_ACKNOLEDGE'])
        self.press_reset()
        self.assertTrue(self.port.command['b_02_ACKNOLEDGE'])

    def test_no_move_ack_fault_and_no_stale_data_score(self):
        self.press_reset()
        self.scan(230)
        self.assertEqual(self.v['FaultCode'], 3)
        self.scan(DataValid=False)
        self.assertFalse(self.v['ResultValid'])
        self.assertTrue(self.port.command['b_01_STOP'])
        self.scan(30, DataValid=True)
        self.assertEqual(self.v['State'], 900)
        self.press_reset()
        self.moving()

    def test_cpu_restart_requires_new_reset(self):
        self.pause_at(13000)
        self.scan(FirstScan=True)
        self.scan(30, FirstScan=False)
        self.assertEqual(self.v['State'], 10)
        self.assertEqual(self.lights(), (False, False, False))
        self.press_reset()
        self.moving()

    def test_chase_and_pause_blink_timing(self):
        self.press_reset()
        self.moving()
        self.assertEqual(self.lights(), (True, False, False))
        self.scan(45)
        self.assertEqual(self.lights(), (False, True, False))
        self.scan(52)
        self.assertEqual(self.lights(), (False, False, True))
        self.scan(52)
        self.assertEqual(self.lights(), (True, False, False))
        self.scan(PauseDI=True)
        self.assertEqual(self.lights(), (False, False, False))
        self.ack()
        self.port.b_04_COMMAND_SUCCESSFULLY_PROCESSED = True
        self.scan(80, PauseDI=False)
        self.assertEqual(self.v['State'], 80)
        self.assertEqual(self.lights(), (True, False, False))
        self.scan(22)
        self.assertEqual(self.lights(), (False, False, False))
        self.scan(52)
        self.assertEqual(self.lights(), (True, False, False))
        self.press_reset()
        self.assertEqual(self.lights(), (True, False, False))
        self.scan(52)
        self.assertEqual(self.lights(), (False, True, False))
