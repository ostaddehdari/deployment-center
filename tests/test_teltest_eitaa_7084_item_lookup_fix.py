"""Regression: item id 392801 is NOT the content_items primary key."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

P = Path(__file__).resolve().parents[1] / "scripts" / "teltest-eitaa-7084-single-video-send-v1.py"
spec = importlib.util.spec_from_file_location("video_send", P)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class TestRealItemJoin(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.db = Path(self.folder.name) / "sample.sqlite3"
        with sqlite3.connect(self.db) as c:
            c.executescript("""
                CREATE TABLE content_items(
                    id INTEGER PRIMARY KEY, external_id TEXT,
                    source_ref TEXT, source_key TEXT, processed_text TEXT,
                    raw_text TEXT,connector_code TEXT);
                CREATE TABLE transfer_job_items(
                    id INTEGER PRIMARY KEY, transfer_job_id INTEGER,
                    content_id INTEGER,destination_id INTEGER,status TEXT);
                CREATE TABLE transfer_destinations(
                    id INTEGER PRIMARY KEY,transfer_job_id INTEGER,
                    enabled INTEGER,provider_code TEXT,destination_ref TEXT);
                INSERT INTO content_items VALUES
                  (17,'7084','https://eitaa.com/channelabc/7084','','original caption','','eitaa'),
                  (392801,'7083','https://eitaa.com/notvideo','','wrong item','','eitaa');
                INSERT INTO transfer_destinations VALUES
                  (1,11,1,'eitaa_user','eitaaacc:00000000000000000000000000000000');
                INSERT INTO transfer_job_items VALUES
                  (392801,11,17,1,'failed');
            """)
        self.old_db = m.DB
        m.DB = self.db
        self.addCleanup(lambda:setattr(m,"DB",self.old_db))
    def test_lookup_uses_foreign_key_and_not_item_id(self):
        cid, keys, ref, caption = m.sources_and_destination()
        self.assertEqual(cid,17)
        self.assertEqual(keys,["channelabc"])
        self.assertEqual(caption,"original caption")
        self.assertTrue(ref.startswith("eitaaacc:"))
    def test_transfer_already_sent_is_rejected(self):
        with sqlite3.connect(self.db) as c:
            c.execute("UPDATE transfer_job_items SET status='transferred' WHERE id=392801")
        with self.assertRaisesRegex(RuntimeError,"VIDEO_ITEM_ALREADY_SENT"):
            m.sources_and_destination()
    def test_journal_stages_uncertain_then_confirmed(self):
        old=m.JOURNAL
        m.JOURNAL=Path(self.folder.name)/"result.json"
        self.addCleanup(lambda:setattr(m,"JOURNAL",old))
        m.journal_write("sending_or_uncertain",17,"abc123")
        first=json.loads(m.JOURNAL.read_text())
        self.assertEqual(first["content_id"],17)
        self.assertEqual(first["transfer_item_id"],392801)
        self.assertEqual(first["status"],"sending_or_uncertain")
        m.journal_write("confirmed_by_gateway",17,"abc123")
        self.assertEqual(json.loads(m.JOURNAL.read_text())["status"],"confirmed_by_gateway")

if __name__ == "__main__":
    unittest.main()
