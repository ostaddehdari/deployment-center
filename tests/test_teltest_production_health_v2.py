"""Verify that the production installer waits for HTTP readiness after restart."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

TARGET=Path(__file__).resolve().parents[1]/"scripts"/"teltest-eitaa-production-media-v2.py"
spec=importlib.util.spec_from_file_location("production_v2",TARGET)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class TestProductionHealthRetry(unittest.TestCase):
    def test_slow_start_does_not_rollback_early(self):
        with patch.object(module,"active",return_value=True), \
             patch.object(module,"health",side_effect=[False,False,True]), \
             patch.object(module.time,"sleep",return_value=None):
            self.assertTrue(module.await_health(20))
    def test_health_must_report_ok(self):
        with patch.object(module,"active",return_value=True), \
             patch.object(module,"health",return_value=True):
            self.assertTrue(module.await_health(1))
    def test_new_installer_does_not_enable_any_timers(self):
        content=TARGET.read_text(encoding="utf8")
        self.assertNotIn('enable","--now"',content)
        self.assertIn('JOB11_PAUSED',content)
        self.assertIn('ROLLBACK_HEALTH_RESTORED=',content)
        self.assertIn('POST_DEPLOY_HEALTH_FAILED',content)
if __name__=="__main__":unittest.main()
