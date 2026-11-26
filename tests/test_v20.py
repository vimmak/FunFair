"""OB1 scan tests: execute the wrapper and game SCL, substitute the PN device."""
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import test_scan_logic as sim


V20 = sim.SOURCE.parent / 'v20'


def load_fb(name):
    with patch.object(sim, 'SOURCE', V20 / (name + '.scl')):
        return sim.ScanModel()


class GameInstance:
    def __init__(self):
        self.fb = load_fb('FB_StopGameV20')

    def call(self, dt, **inputs):
        self.fb.scan(**inputs)

    def __getattr__(self, name):
        return self.fb.v[name]


class NativePort(SimpleNamespace):
    """Native cyclic FB boundary. Tests supply device feedback explicitly."""
    def call(self, dt, **inputs):
        self.command = inputs
        assert inputs['b_RELEASE_FUNCTION_BLOCK'] and inputs['b_00_FAST_STOP']
        assert not (inputs['b_01_STOP'] and inputs['b_13_MOVE_TO_ABSOLUTE_POSITION'])


class AutoGame(unittest.TestCase):
    def setUp(self):
        self.ob = load_fb('FB_FunFairEGU_V20')
        self.port = NativePort(b_00_READY_FOR_OPERATION=True,
            b_01_CONTOL_AUTHORITY_FIELDBUS=True, b_07_ERROR=False,
            b_03_NOT_FEASIBLE=False, b_04_COMMAND_SUCCESSFULLY_PROCESSED=False,
            b_13_POSITION_REACHED=False, b_05_COMMAND_RECEIVED_TOGGLE=False,
            di_ACTUAL_POSITION=1000, i_DIAGNOSIS_ERROR=0)
        self.v = self.ob.v
        self.v.update(Game=GameInstance(), EGU=self.port, OpenPosition_um=1000,
            ClosePosition_um=23000, TargetPosition_um=13000, Tolerance_um=2000,
            Velocity_um_s=2000, FirstScan=True, InputHW=278, OutputHW=277)
        self.scan()
        self.v['FirstScan'] = False

    def scan(self, n=1, **inputs):
        self.v.update(inputs)
        for _ in range(n):
            self.ob.run(self.ob.code, 5)

    def ack(self):
        self.port.b_05_COMMAND_RECEIVED_TOGGLE ^= True
        self.scan()

    def moving(self):
        self.scan(16)
        self.assertTrue(self.port.command['b_13_MOVE_TO_ABSOLUTE_POSITION'])
        self.ack()
        self.assertEqual(self.v['State'], 50)

    def pause_at(self, position):
        self.moving()
        self.scan(PauseDI=True)
        self.assertTrue(self.port.command['b_01_STOP'])
        self.ack()
        self.port.di_ACTUAL_POSITION = position
        self.port.b_04_COMMAND_SUCCESSFULLY_PROCESSED = True
        self.scan(20)
        self.assertFalse(self.v['ResultValid'])
        self.scan(25)
        self.assertTrue(self.v['ResultValid'])

    def test_auto_reverse_and_native_setpoints(self):
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

    def test_boot_locked_or_offline_never_moves(self):
        self.port.b_00_READY_FOR_OPERATION = False
        self.scan(20, FirstScan=True, PauseDI=True)
        self.port.b_00_READY_FOR_OPERATION = True
        self.scan(30, FirstScan=False)
        self.assertFalse(self.v['ResultValid'])
        self.assertFalse(self.port.command['b_13_MOVE_TO_ABSOLUTE_POSITION'])
        self.scan(PauseDI=False)
        self.moving()

    def test_score_pins_and_unlock(self):
        self.pause_at(11900)
        self.assertEqual((self.v['ActualPosition_um'], self.v['SignedError_um']), (11900, -1100))
        self.assertTrue(self.v['Success'])
        self.scan(30, ResetButton=True, TargetPosition_um=8000)
        self.assertEqual(self.v['State'], 80)
        self.assertFalse(self.port.command['b_02_ACKNOLEDGE'])
        self.scan(PauseDI=False)
        self.assertFalse(self.v['ResultValid'])
        self.assertEqual(self.v['SignedError_um'], 3900)
        self.moving()

    def test_boundary_misses(self):
        self.pause_at(15000)
        self.assertFalse(self.v['Success'])

    def test_early_unlock_waits_for_stop_ack_and_settling(self):
        self.scan(16)
        self.scan(PauseDI=True)
        self.assertEqual(self.v['State'], 55)
        self.scan(PauseDI=False)
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
        self.assertEqual(self.v['State'], 40)

    def test_reset_only_acknowledges_device(self):
        self.moving()
        self.port.b_07_ERROR = True
        self.port.i_DIAGNOSIS_ERROR = 0xCA
        self.scan()
        self.assertEqual((self.v['FaultCode'], self.v['GripperFaultCode']), (1, 0xCA))
        self.scan(8, ResetButton=True)
        self.assertTrue(self.port.command['b_02_ACKNOLEDGE'])
        self.port.b_07_ERROR = False
        self.port.i_DIAGNOSIS_ERROR = 0
        self.scan(30, ResetButton=False)
        self.assertEqual(self.v['State'], 900)
        self.assertFalse(self.port.command['b_02_ACKNOLEDGE'])
        self.scan(PauseDI=True)
        self.scan(PauseDI=False)
        self.moving()

    def test_no_ack_and_no_stale_data_score(self):
        self.scan(230)
        self.assertEqual(self.v['FaultCode'], 3)
        self.scan(DataValid=False)
        self.assertFalse(self.v['ResultValid'])
        self.assertTrue(self.port.command['b_01_STOP'])
