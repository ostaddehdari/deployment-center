import ast
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / "scripts"

def load(name, path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

media=load("media", "eitaa_authenticated_media.py")
installer=load("installer", "teltest-eitaa-production-media-v1.py")

class ProductionMediaContract(unittest.TestCase):
    def test_usernames_are_channel_scoped(self):
        self.assertEqual(media.username("eitaa:screenshotpersian"),"screenshotpersian")
        self.assertEqual(media.username("https://eitaa.com/s/screenshotpersian/7084"),"screenshotpersian")
        self.assertEqual(media.username("https://example.net/s/screenshotpersian/7084"),"")
        self.assertEqual(media.username("https://eitaa.com.evil.net/x"),"")
    def test_video_descriptor_valid(self):
        d={"media":{"document":{
            "id":"123456789", "access_hash":"-119922", "size":10095369,
            "mime_type":"video/mp4","file_reference":list(range(29)),
            "attributes":[{"_":"documentAttributeVideo"}]}}}
        self.assertEqual(media.descriptor(d)[3:],(10095369,".mp4"))
    def test_missing_reference_is_rejected(self):
        d={"media":{"document":{
            "id":"123", "access_hash":"456", "size":1024,
            "mime_type":"video/mp4"}}}
        with self.assertRaises(media.EitaaMediaSourceError):media.descriptor(d)
    def test_html_host_not_authenticated(self):
        import asyncio
        with tempfile.TemporaryDirectory() as td:
            got=asyncio.run(media.download_eitaa_authenticated(
                "https://eitaa.com.evil.org/post",td,0,
                {"connector_code":"eitaa","external_id":"7084"},kind="video"))
            self.assertIsNone(got)
    def test_js_scope_replacement(self):
        stub=(
          "// TELTEST_EITAA_GATEWAY_ACCESS_CONTROL_V1\n"
          "// TELTEST_EITAA_VIDEO_7084_20_CHUNKS_V1\n"
          "const timingSafeEqual = true;\napp.listen(port, '127.0.0.1',()=>{});\n"
          "        // TELTEST_EITAA_VIDEO_READ_SCOPE_V1\n"
          "        app.use('/eitaa/messages/read',(req,res,next)=>{next();\n        });\n"
          "        // TELTEST_EITAA_VIDEO_FIRST_CHUNK_V1\n"
          "        app.use('/eitaa/messages/getFile',(req,res,next)=>{next();\n        });\n"
        )
        result=installer.replace_block(stub,installer.READ_MARK,installer.NEW_READ)
        result=installer.replace_block(result,installer.FILE_MARK,installer.NEW_FILE)
        self.assertIn("TELTEST_EITAA_PRODUCTION_MEDIA_V1_READ",result)
        self.assertIn("TELTEST_EITAA_PRODUCTION_MEDIA_V1_FILE",result)
        self.assertIn("268435456-524288",result)
        self.assertNotIn("videoProbeNextOffset",result)

if __name__=="__main__":unittest.main()
