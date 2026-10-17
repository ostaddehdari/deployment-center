#!/usr/bin/env python3
"""Use a compatible local/container pg_dump for the exact configured endpoint."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

TABLES = ['index_forms', 'index_form_versions', 'index_form_fields',
          'index_form_options', 'index_form_rules', 'content_type_index_forms']

def run(args):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None

def major(args):
    result = run(args + ['--version'])
    match = re.search(r'PostgreSQL\)\s+(\d+)', result.stdout) if result and result.returncode == 0 else None
    return int(match.group(1)) if match else 0

def select_dump(server_major, host, port):
    paths = [os.environ.get('ZOHA_PG_DUMP', ''),
             f'/usr/lib/postgresql/{server_major}/bin/pg_dump',
             shutil.which('pg_dump') or '']
    local = []
    for name in dict.fromkeys(paths):
        if name and Path(name).is_file() and os.access(name, os.X_OK):
            version = major([name])
            if version >= server_major:
                local.append((version, name))
    if local:
        version, name = min(local, key=lambda x: (x[0] != server_major, x[0]))
        return [name, '--host', host, '--port', str(port)], f'local PostgreSQL {version}'

    docker = shutil.which('docker')
    if docker and host == '127.0.0.1':
        result = run([docker, 'ps', '-q'])
        for container in result.stdout.split() if result and result.returncode == 0 else []:
            result = run([docker, 'inspect', '--format', '{{json .NetworkSettings.Ports}}', container])
            if not result or result.returncode:
                continue
            try:
                ports = json.loads(result.stdout) or {}
            except (ValueError, TypeError):
                continue
            inner_port = None
            for key, bindings in ports.items():
                if not key.endswith('/tcp'):
                    continue
                if any(str(binding.get('HostPort')) == str(port) and
                       binding.get('HostIp') in ('', '0.0.0.0', '127.0.0.1', '::', '::1')
                       for binding in bindings or []):
                    inner_port = key.split('/')[0]
                    break
            if inner_port is None:
                mode = run([docker, 'inspect', '--format', '{{.HostConfig.NetworkMode}}', container])
                if mode and mode.returncode == 0 and mode.stdout.strip() == 'host':
                    inner_port = str(port)
            if inner_port is None:
                continue
            version = major([docker, 'exec', container, 'pg_dump'])
            if version >= server_major:
                return [docker, 'exec', '-e', 'PGPASSWORD', '-e', 'PGCONNECT_TIMEOUT',
                        container, 'pg_dump', '--host', '127.0.0.1', '--port', inner_port], \
                       f'container PostgreSQL {version} (verified host port {port})'
    raise RuntimeError(f'No compatible pg_dump for PostgreSQL {server_major}. '
                       f'PostgreSQL {server_major} client must be available locally or in the database container.')

def backup(output, server_major, host='127.0.0.1', port=5433):
    command, provider = select_dump(server_major, host, port)
    target = Path(output)
    temporary = target.with_suffix(target.suffix + '.partial')
    if target.exists() or temporary.exists():
        raise RuntimeError('Backup destination already exists; refusing to replace it.')
    command += ['--username', 'zoha_app', '--dbname', 'zoha_core', '--no-password',
                '--data-only', '--inserts', '--lock-wait-timeout=15000']
    command += [f'--table=zoha.{name}' for name in TABLES]
    environment = os.environ.copy()
    environment['PGCONNECT_TIMEOUT'] = '10'
    try:
        with temporary.open('xb') as stream:
            os.chmod(temporary, 0o600)
            result = subprocess.run(command, stdout=stream, env=environment, check=False)
            stream.flush()
            os.fsync(stream.fileno())
        if result.returncode:
            raise RuntimeError(f'pg_dump failed with exit code {result.returncode}; no migration was started.')
        if b'-- PostgreSQL database dump complete' not in temporary.read_bytes():
            raise RuntimeError('Backup completion marker is missing; no migration was started.')
        temporary.replace(target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix('.sql.sha256').write_text(f'{digest}  {target.name}\n')
    print(f'PG_DUMP_PROVIDER={provider}')
    print(f'DB_BACKUP={target}')
    print(f'DB_BACKUP_SHA256={digest}')
    print('DB_BACKUP=PASS')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--server-major', type=int, required=True)
    args = parser.parse_args()
    try:
        backup(args.output, args.server_major)
    except Exception as error:
        print(f'ERROR: {error}', file=sys.stderr)
        sys.exit(1)
