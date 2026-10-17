import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('backup',Path(__file__).with_name('backup_index_forms.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class BackupTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.log=self.root/'calls.jsonl'
  self.env=patch.dict(os.environ,{'PGPASSWORD':'test-only','DUMP_TRACE':str(self.log)},clear=False);self.env.start()
 def tearDown(self):self.env.stop();self.temp.cleanup()
 def executable(self,name,code):
  p=self.root/name;p.write_text('#!/usr/bin/env python3\n'+code);p.chmod(0o755);return str(p)
 def trace(self):return [json.loads(x) for x in self.log.read_text().splitlines()]
 def dump_program(self,version=17,fail=False,marker=True):
  return self.executable('pg_dump_test',f'''import sys,os,json
with open(os.environ['DUMP_TRACE'],'a') as f:f.write(json.dumps(sys.argv[1:])+'\\n')
if '--version' in sys.argv:print('pg_dump (PostgreSQL) {version}.11');sys.exit(0)
print('-- PostgreSQL database dump')
print("INSERT INTO zoha.index_forms VALUES ('test');")
{'print("-- PostgreSQL database dump complete")' if marker else ''}
sys.exit({2 if fail else 0})
''')
 def test_compatible_local_client_and_private_backup(self):
  binary=self.dump_program();output=self.root/'backup.sql'
  with patch.dict(os.environ,{'ZOHA_PG_DUMP':binary}),contextlib.redirect_stdout(io.StringIO()):m.backup(output,17)
  self.assertTrue(output.read_text().endswith('-- PostgreSQL database dump complete\n'))
  self.assertEqual(output.stat().st_mode&0o777,0o600)
  self.assertTrue(output.with_suffix('.sql.sha256').exists())
  calls=self.trace();self.assertTrue(any('--no-password' in args for args in calls));self.assertFalse(any('test-only' in x for args in calls for x in args))
 def test_failed_dump_does_not_leave_successful_backup(self):
  binary=self.dump_program(fail=True);output=self.root/'backup.sql'
  with patch.dict(os.environ,{'ZOHA_PG_DUMP':binary}),self.assertRaises(RuntimeError):m.backup(output,17)
  self.assertFalse(output.exists());self.assertFalse(output.with_suffix('.sql.partial').exists())
 def test_zero_exit_without_completion_marker_is_rejected(self):
  binary=self.dump_program(marker=False);output=self.root/'backup.sql'
  with patch.dict(os.environ,{'ZOHA_PG_DUMP':binary}),self.assertRaises(RuntimeError):m.backup(output,17)
  self.assertFalse(output.exists())
 def test_existing_backup_is_not_replaced(self):
  binary=self.dump_program();output=self.root/'backup.sql';output.write_text('previous')
  with patch.dict(os.environ,{'ZOHA_PG_DUMP':binary}),self.assertRaises(RuntimeError):m.backup(output,17)
  self.assertEqual(output.read_text(),'previous')
 def test_old_local_client_falls_back_only_to_matching_container(self):
  old=self.dump_program(version=16)
  docker=self.executable('docker_test',r'''import sys,json,os
args=sys.argv[1:]
with open(os.environ['DUMP_TRACE'],'a') as f:f.write(json.dumps(args)+'\n')
if args[:2]==['ps','-q']:print('unrelated\nactual')
elif args[0]=='inspect':
 if 'NetworkMode' in args[2]:print('bridge')
 else:print(json.dumps({'5432/tcp':[{'HostIp':'127.0.0.1','HostPort':'5433' if args[-1]=='actual' else '15432'}]}))
elif args[0]=='exec' and '--version' in args:print('pg_dump (PostgreSQL) 17.11')
elif args[0]=='exec':
 assert 'actual' in args and args[args.index('--port')+1]=='5432'
 assert 'PGPASSWORD' in args and not any(x.startswith('PGPASSWORD=') for x in args)
 print('-- PostgreSQL database dump\n-- PostgreSQL database dump complete')
else:sys.exit(9)
''')
  output=self.root/'backup.sql'
  original_major=m.major
  with patch.dict(os.environ,{'ZOHA_PG_DUMP':old}),patch.object(m.shutil,'which',side_effect=lambda name:docker if name=='docker' else None),patch.object(m,'major',side_effect=lambda args:original_major(args) if args[0] in (old,docker) else 0),contextlib.redirect_stdout(io.StringIO()):m.backup(output,17)
  calls=self.trace();self.assertTrue(output.exists());self.assertFalse(any('unrelated' in args and args[0]=='exec' for args in calls));self.assertFalse(any('--data-only' in args and args[0]!='exec' for args in calls))
 def test_no_compatible_provider_stops_safely(self):
  old=self.dump_program(version=16)
  original_major=m.major
  with patch.dict(os.environ,{'ZOHA_PG_DUMP':old}),patch.object(m.shutil,'which',return_value=None),patch.object(m,'major',side_effect=lambda args:original_major(args) if args[0]==old else 0),self.assertRaises(RuntimeError):m.select_dump(17,'127.0.0.1',5433)

if __name__=='__main__':unittest.main(verbosity=2)
