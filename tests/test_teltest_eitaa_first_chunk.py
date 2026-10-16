import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1] / 'scripts'
spec=importlib.util.spec_from_file_location('chunk',ROOT/'teltest-eitaa-video-first-chunk-route-v1.py')
patcher=importlib.util.module_from_spec(spec)
spec.loader.exec_module(patcher)

class FirstChunkOnly(unittest.TestCase):
    def setUp(self):
        self.py='''# TELTEST_EITAA_SECURED_CLIENT_V1
# TELTEST_EITAA_VIDEO_READ_ROUTE_V1
def gateway(path: str, body: dict, timeout: int = 30) -> dict:
    allowed={"messages/dialogs", "messages/read", "messages/send", "messages/sendMedia"}
    return {}
'''
        self.js="""// TELTEST_EITAA_GATEWAY_ACCESS_CONTROL_V1
// TELTEST_EITAA_VIDEO_READ_SCOPE_V1
const allowedRoutes = new Set([
            'POST /eitaa/messages/read',
]);
const timingSafeEqual = true;
app.listen(port, '127.0.0.1', ()=>{});
        app.use(express.json());
"""
    def test_only_getfile_first_chunk(self):
        p,j=patcher.patch(self.py,self.js)
        self.assertIn('"messages/getFile"',p)
        self.assertIn("'POST /eitaa/messages/getFile'",j)
        self.assertIn("Number(b.offset) === 0",j)
        self.assertIn("videoProbeUsed = true",j)
        self.assertIn("byteRef && !videoProbeUsed",j)
        self.assertIn("b.type === 'document'",j)
        self.assertIn("app.listen(port, '127.0.0.1'",j)
    def test_idempotence(self):
        p,j=patcher.patch(self.py,self.js)
        with self.assertRaises(RuntimeError): patcher.patch(p,j)
    def test_rejects_public_listener(self):
        with self.assertRaises(RuntimeError):
            patcher.patch(self.py,self.js.replace("'127.0.0.1'","'0.0.0.0'"))
    def test_rejects_missing_read_route(self):
        with self.assertRaises(RuntimeError):
            patcher.patch(self.py,self.js.replace('TELTEST_EITAA_VIDEO_READ_SCOPE_V1','REMOVED'))
    def test_no_changes_to_send_route(self):
        p,j=patcher.patch(self.py,self.js)
        self.assertEqual(p.count('"messages/send"'),1)
        self.assertNotIn('messages/delete',p)
        self.assertNotIn('messages/forward',p)

if __name__=='__main__': unittest.main()
