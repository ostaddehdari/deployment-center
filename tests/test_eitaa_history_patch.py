import importlib.util
from pathlib import Path
import tempfile
import unittest

FILE = Path(__file__).resolve().parents[1] / 'scripts' / 'teltest-eitaa-history-route-v1.py'
spec = importlib.util.spec_from_file_location('history', FILE)
history = importlib.util.module_from_spec(spec)
spec.loader.exec_module(history)

class TestScopedHistoryPatch(unittest.TestCase):
    def setUp(self):
        self.py = '''# TELTEST_EITAA_SECURED_CLIENT_V1\ndef gateway(path: str, body: dict, timeout: int = 30) -> dict:\n    if path not in {"messages/dialogs", "messages/send", "messages/sendMedia"}:\n        raise RuntimeError()\n    return {}\n'''
        self.js = '''const allowedRoutes = new Set([\n            'POST /eitaa/messages/dialogs',\n]);\n// TELTEST_EITAA_GATEWAY_ACCESS_CONTROL_V1\nconst timingSafeEqual = true;\napp.listen(port, '127.0.0.1', () => {});\n        app.use(express.json());\n'''
    def test_scope(self):
        py,js = history.patch(self.py,self.js)
        self.assertIn('"messages/read"',py)
        self.assertIn("'POST /eitaa/messages/read'",js)
        self.assertIn('offset !== 7085 || size !== 3',js)
        self.assertNotIn('"messages/getFile"',py)
    def test_idempotent(self):
        py,js = history.patch(self.py,self.js)
        with self.assertRaises(RuntimeError):history.patch(py,js)
    def test_public_listener_rejected(self):
        with self.assertRaises(RuntimeError):history.patch(self.py,self.js.replace("'127.0.0.1'","'0.0.0.0'"))

if __name__=='__main__':unittest.main()
