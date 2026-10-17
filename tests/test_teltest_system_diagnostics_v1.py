import importlib.util
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

S = Path(__file__).resolve().parents[1] / "scripts"

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,S/path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

installer=load("installer","teltest-install-system-diagnostics-v1.py")
collector=load("collector","teltest_system_journal_collector.py")

class TestJobSystemUI(unittest.TestCase):
    def test_patch_is_mounted_in_authenticated_operations_screen(self):
        python_src = """def init_operations_center(app, login_required, api_post_required, telegram_client, account_get):
    init_operations_schema()
    migrated_hashtags = bootstrap_hashtags()
    @app.get('/teltest/some-path')
    @login_required
    def home(): pass
"""
        html="<html><body><h1>TelTest</h1></body></html>"
        modified, rendered=installer.patch(python_src,html)
        self.assertIn("register_system_diagnostics(app, login_required)",modified)
        self.assertIn("teltest-system-diagnostics.js",rendered)
        self.assertIn("teltest-system-diagnostics.css",rendered)
        with self.assertRaisesRegex(RuntimeError,"ALREADY_PATCHED"):
            installer.patch(modified,rendered)
    def test_system_logs_expose_no_raw_access_hash(self):
        self.assertEqual(collector.scrub("file_reference=123"),"[Sensitive line withheld]")
        self.assertNotIn("https://eitaa.com",collector.scrub("failed https://eitaa.com/channel/123"))
        self.assertNotIn("+989121234567",collector.scrub("error for +989121234567"))
    def test_journal_never_sends_or_enqueues(self):
        src=(S/"teltest_system_journal_collector.py").read_text()
        self.assertNotIn("sendMedia",src)
        self.assertNotIn("enqueue(",src)
    def test_diagnostic_timer_not_job_timer(self):
        src=(S/"teltest-install-system-diagnostics-v1.py").read_text()
        self.assertIn('"teltest-system-journal.timer"',src)
        self.assertNotIn('enable","--now","teltest-delivery.timer"',src)
        self.assertIn("login_required", (S/"teltest_job_system_diagnostics.py").read_text())
if __name__=="__main__":
    unittest.main()
