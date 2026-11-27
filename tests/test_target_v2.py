import unittest
from unittest.mock import patch

import test_scan_logic as sim


class MovingTarget(unittest.TestCase):
    def setUp(self):
        with patch.object(sim, 'SOURCE', sim.SOURCE.parent / 'v20' / 'FB_FunFairTarget.scl'):
            self.target = sim.ScanModel()
        self.scan(FirstScan=True, GameState=0, HighDifficulty=True,
                         ClosePosition_um=22000, OpenPosition_um=1000, FixedTarget_um=13000)

    def scan(self, n=1, **values):
        self.target.v.update(values)
        for _ in range(n):
            self.target.run(self.target.code, 5)
        return self.target.v

    def test_reversed_endpoints_and_eased_motion(self):
        self.assertEqual(self.target.v['ActiveMode'], 1)
        frame = self.scan(FirstScan=False, GameState=50)
        self.assertEqual((frame['ActiveMode'], frame['Target_um']), (2, 22000))
        first_duration = frame['Duration_ms']
        self.assertTrue(2300 <= first_duration <= 5200)
        self.scan(2)
        quarter = self.scan(first_duration // 20)['Target_um']
        middle = self.scan(first_duration // 20)['Target_um']
        self.assertGreater(22000 - quarter, 0)
        self.assertLess(22000 - quarter, quarter - middle)
        while frame['TowardsOpen']:
            self.scan()
        self.assertEqual(frame['Target_um'], 1000)
        self.assertNotEqual(frame['Duration_ms'], first_duration)
        self.assertGreater(self.scan(150)['Target_um'], 1000)

    def test_pause_holds_target_and_defers_switch(self):
        original = self.scan(180, FirstScan=False, GameState=50)['Target_um']
        self.assertEqual(self.scan(GameState=55)['Target_um'], original)
        frame = self.scan(100, GameState=80, HighDifficulty=False)
        self.assertEqual((frame['ActiveMode'], frame['Target_um']), (2, original))
        self.assertEqual(self.scan(GameState=30, HighDifficulty=True)['Target_um'], original)
        self.assertLess(self.scan(120)['Target_um'], original)
        frame = self.scan(HighDifficulty=False)
        self.assertEqual((frame['ActiveMode'], frame['Target_um']), (1, 13000))

    def test_bool_change_during_pause_applies_when_motion_resumes(self):
        self.scan(120, FirstScan=False, GameState=50)
        frame = self.scan(GameState=60, HighDifficulty=False)
        self.assertEqual(frame['ActiveMode'], 2)
        self.assertEqual(self.scan(GameState=80)['ActiveMode'], 2)
        frame = self.scan(GameState=30)
        self.assertEqual((frame['ActiveMode'], frame['Target_um']), (1, 13000))
