import importlib.util
from pathlib import Path
import unittest

BASE = Path(__file__).resolve().parents[1]
SCRIPT = BASE / "scripts" / "teltest-eitaa-7084-twenty-chunks-v1.py"
spec = importlib.util.spec_from_file_location("expand",SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class TwentyChunkPatchTests(unittest.TestCase):
    def setUp(self):
        self.py = "# TELTEST_EITAA_VIDEO_FIRST_CHUNK_V1\n"
        self.js = """// TELTEST_EITAA_VIDEO_FIRST_CHUNK_V1
const timingSafeEqual = true;
app.listen(port, '127.0.0.1', ()=>{});
        let videoProbeUsed = false;
        app.use('/eitaa/messages/getFile', (req, res, next) => {
          const b = req.body || {};
          const ref = b.file_reference;
          const byteRef = true;
          const ok = Number(b.offset) === 0 && byteRef && !videoProbeUsed;
          if (!ok) return;
            videoProbeUsed = true;
          next();
        });
"""
    def test_strict_20_offsets(self):
        _, js = m.transform(self.py, self.js)
        self.assertIn("Number(b.offset) % 524288 === 0",js)
        self.assertIn("Number(b.offset) <= 9961472",js)
        self.assertIn("Number(b.offset) === videoProbeNextOffset",js)
        self.assertIn("videoProbeNextOffset += 524288",js)
    def test_same_doc_pinned(self):
        _, js = m.transform(self.py,self.js)
        self.assertIn("videoProbeIdentity === null || videoProbeIdentity === JSON.stringify",js)
        self.assertIn("videoProbeIdentity = JSON.stringify",js)
    def test_reject_repatch(self):
        p,j=m.transform(self.py,self.js)
        with self.assertRaises(RuntimeError):m.transform(p,j)
    def test_reject_public_listener(self):
        with self.assertRaises(RuntimeError):
            m.transform(self.py,self.js.replace("'127.0.0.1'","'0.0.0.0'"))
    def test_sends_are_independent(self):
        self.assertIn("sendMedia", (BASE/"scripts/teltest-eitaa-7084-single-video-send-v1.py").read_text())
        self.assertIn("JOURNAL", (BASE/"scripts/teltest-eitaa-7084-single-video-send-v1.py").read_text())
        self.assertIn("EXPECTED_FIRST_SHA256", (BASE/"scripts/teltest-eitaa-7084-single-video-send-v1.py").read_text())

if __name__ == "__main__":
    unittest.main()
