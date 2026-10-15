#!/usr/bin/env python3
"""Local best-effort Git safety gate. Never prints secret values.
Not a replacement for review, server-side secret scanning, or database backups.
"""
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

DENY_DIRS = {'.git', '.ssh', '.cloudflared', 'private', 'reports', 'backups', 'backup',
             'secrets', 'media', 'uploads', 'data', 'pgdata', 'logs', '__pycache__',
             'staticfiles', '.venv', 'venv', 'node_modules'}
SAFE_TOP = {'.gitignore', '.gitattributes', '.env.example', 'README.md', 'CHANGELOG.md',
            'compose.yaml', 'requirements.txt', 'pmctl'}
SAFE_ROOTS = {'app', 'ops', 'db-init', 'docs', 'tools', '.githooks', '.github'}
SAFE_EXT = {'.py', '.html', '.css', '.js', '.md', '.txt', '.sh', '.json', '.yaml', '.yml'}
MAX_FILE = 2 * 1024 * 1024
PATTERNS = [
    re.compile(rb'-----BEGIN (?:OPENSSH |RSA |EC |DSA |ENCRYPTED )?PRIVATE KEY-----'),
    re.compile(rb'\bgh[pousr]_[A-Za-z0-9]{30,}\b'),
    re.compile(rb'\bgithub_pat_[A-Za-z0-9_]{35,}\b'),
    re.compile(rb'\bAKIA[A-Z0-9]{16}\b'),
    re.compile(rb'\beyJ[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b'),
    re.compile(rb'(?:postgres(?:ql)?|mysql)://[^\s:/]+:[^\s@/]+@', re.I),
]


def forbidden_path(name):
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or not p.parts:
        return True
    if any(c in name for c in ('\n', '\r', '\t', '\\')):
        return True
    if any(part.lower() in DENY_DIRS for part in p.parts):
        return True
    if p.name.lower().startswith('.env') and name != '.env.example':
        return True
    if any(part.lower().startswith(('id_rsa', 'id_ed25519')) for part in p.parts):
        return True
    if name in SAFE_TOP or name in {'.githooks/pre-commit', '.githooks/pre-push'}:
        return False
    return p.parts[0] not in SAFE_ROOTS or p.suffix.lower() not in SAFE_EXT


def known_secrets(root=Path('/opt/multitek-pm')):
    """Read only relevant local PM secrets into memory; never copy them."""
    values = []
    paths = [root / '.env', root / 'private/bootstrap.env', root / 'private/login.txt']
    for path in paths:
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 131072:
                continue
            text = path.read_text()
        except (OSError, UnicodeError):
            continue
        for line in text.splitlines():
            m = re.match(r'^\s*([A-Za-z_][A-Za-z0-9_ ]*)\s*[=:]\s*(.*?)\s*$', line)
            if not m or not re.search(r'password|secret|token|api_key', m[1], re.I):
                continue
            value = m[2].strip().strip('"\'')
            if len(value) >= 8 and not value.startswith(('CHANGE_ME', 'REPLACE_ME')):
                values.append(value.encode())
    return values


def inspect_blob(path, mode, data, secrets):
    if mode not in ('100644', '100755'):
        raise ValueError('File khusus/symlink tidak diizinkan: ' + path)
    if forbidden_path(path):
        raise ValueError('Path belum diizinkan atau termasuk data privat: ' + path)
    if len(data) > MAX_FILE or b'\0' in data:
        raise ValueError('Biner/file terlalu besar; perlu review terpisah: ' + path)
    try:
        data.decode('utf-8')
    except UnicodeError:
        raise ValueError('Bukan teks UTF-8: ' + path)
    if any(s in data for s in secrets) or any(p.search(data) for p in PATTERNS):
        raise ValueError('Kemungkinan kredensial ditemukan; konten disembunyikan: ' + path)


def git(*args):
    p = subprocess.run(['git', *args], capture_output=True)
    if p.returncode:
        raise ValueError('Pemeriksaan Git gagal: ' + args[0])
    return p.stdout


def scan_index(secrets):
    count = 0
    for entry in git('ls-files', '--stage', '-z').split(b'\0'):
        if not entry:
            continue
        meta, raw_path = entry.split(b'\t', 1)
        mode, oid, stage = meta.decode().split()
        path = raw_path.decode('utf-8')
        if stage != '0':
            raise ValueError('Konflik belum diselesaikan: ' + path)
        inspect_blob(path, mode, git('cat-file', 'blob', oid), secrets)
        count += 1
    if not count:
        raise ValueError('Tidak ada file terlacak untuk diperiksa.')
    return count


def scan_history(refs, secrets):
    seen = set()
    commits = set()
    for ref in refs:
        if not re.fullmatch(r'[0-9a-f]{40,64}', ref):
            raise ValueError('Object ID push tidak valid.')
        commits.update(git('rev-list', ref).decode().splitlines())
    for commit in sorted(commits):
        for entry in git('ls-tree', '-r', '-z', commit).split(b'\0'):
            if not entry:
                continue
            meta, raw_path = entry.split(b'\t', 1)
            mode, kind, oid = meta.decode().split()
            path = raw_path.decode('utf-8')
            if (path, oid, mode) in seen:
                continue
            if kind != 'blob':
                raise ValueError('Submodule tidak diizinkan otomatis: ' + path)
            inspect_blob(path, mode, git('cat-file', 'blob', oid), secrets)
            seen.add((path, oid, mode))
    return len(seen)


def main():
    try:
        mode = sys.argv[1] if len(sys.argv) > 1 else '--stage'
        secrets = known_secrets()
        if mode == '--stage':
            count = scan_index(secrets)
        elif mode == '--push':
            refs = []
            for line in sys.stdin:
                fields = line.split()
                if len(fields) != 4:
                    raise ValueError('Input pre-push tidak valid.')
                if set(fields[1]) != {'0'}:
                    refs.append(fields[1])
            count = scan_history(refs, secrets)
        else:
            raise ValueError('Mode: --stage atau --push')
        print('PASS guard Git: %d file/blob diperiksa; tetap review diff.' % count)
    except Exception as exc:
        print('STOP GUARD: ' + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
