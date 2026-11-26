import unittest
from unittest.mock import patch
import test_scan_logic as sim


class TwoButtons(unittest.TestCase):
    def setUp(self):
        with patch.object(sim, 'SOURCE', sim.SOURCE.parent/'v20'/'FB_StopGameV20.scl'):
            self.m = sim.ScanModel()
        self.m.scan(FirstScan=True, StartDI=True)
        self.m.scan(20, FirstScan=False)
        self.assertEqual(self.m.v['State'], 10)
        self.m.scan(3, StartDI=False)
        self.assertEqual(self.m.v['State'], 20)

    def test_press_pause_resume(self):
        m = self.m
        m.scan(20, StartDI=True)
        m.scan(ReceivedToggle=True)
        m.scan(StartDI=False)
        self.assertEqual(m.v['State'], 50)
        m.scan(PauseDI=True)
        self.assertTrue(m.v['ControlledStop'])
        m.scan(PauseDI=False)
        m.finish_stop()
        self.assertTrue(m.v['ResultValid'])
        m.scan(StartDI=True)
        self.assertEqual(m.v['State'], 30)

    def test_simultaneous_and_held_start(self):
        m = self.m
        m.scan(StartDI=True, PauseDI=True)
        m.scan(20, PauseDI=False)
        self.assertEqual(m.v['State'], 20)
        m.scan(StartDI=False)
        m.scan(20, StartDI=True)
        m.scan(PauseDI=True)
        self.assertEqual(m.v['State'], 55)
        m.scan(ReceivedToggle=True)
        self.assertEqual(m.v['State'], 60)
        m.finish_stop()
        m.scan(20, PauseDI=False)
        self.assertEqual(m.v['State'], 80)

    def test_manual_fault_ack_and_separate_restart(self):
        m = self.m
        m.scan(DeviceError=True)
        self.assertTrue(m.v['ControlledStop'])
        m.scan(8, ResetButton=True)
        self.assertTrue(m.v['DeviceAck'])
        self.assertFalse(m.v['ControlledStop'])
        m.scan(DeviceError=False)
        self.assertFalse(m.v['DeviceAck'])
        self.assertEqual(m.v['State'], 900)
        m.scan(ResetButton=False)
        m.scan(8, ResetButton=True)
        self.assertEqual(m.v['State'], 80)
        self.assertFalse(m.v['MoveAbsolute'])

    def test_permission_loss_stops_accepted_move(self):
        m = self.m
        m.scan(20, StartDI=True)
        m.scan(ReceivedToggle=True)
        self.assertTrue(m.v['MoveAbsolute'])
        m.scan(MotionPermit=False)
        self.assertFalse(m.v['MoveAbsolute'])
        self.assertTrue(m.v['ControlledStop'])
        m.scan(MotionPermit=True)
        self.assertEqual(m.v['State'], 900)

    def test_startup_waits_for_feedback_and_fresh_start(self):
        m = self.m
        m.scan(FirstScan=True, Ready=False, FieldbusControl=False)
        m.scan(10, FirstScan=False, StartDI=True)
        self.assertEqual(m.v['State'], 0)
        m.scan(10, Ready=True, FieldbusControl=True)
        self.assertEqual(m.v['State'], 10)
        m.scan(StartDI=False)
        m.scan(20, StartDI=True)
        self.assertTrue(m.v['MoveAbsolute'])

    def test_reset_reveals_invalid_speed_then_runs_both_directions(self):
        m = self.m
        m.scan(Ready=False)
        m.scan(8, Ready=True, ResetButton=True, Velocity_um_s=2000,
               VerifiedMinVelocity_um_s=5000)
        self.assertEqual(m.v['FaultCode'], 2)
        m.scan(ResetButton=False, Velocity_um_s=5000)
        m.scan(8, ResetButton=True)
        m.scan(ResetButton=False)
        m.scan(20, StartDI=True)
        for toggle, endpoint, following in [(True, 50000, 10000), (False, 10000, 50000)]:
            self.assertEqual(m.v['PositionCommand_um'], endpoint)
            m.scan(ReceivedToggle=toggle)
            m.scan(ActualPosition_um=endpoint, PositionReached=True, CommandDone=True)
            m.scan(20)
            self.assertEqual(m.v['PositionCommand_um'], following)
            self.assertTrue(m.v['MoveAbsolute'])
