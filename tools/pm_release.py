#!/usr/bin/env python3
"""Check or publish a version tag. Does NOT deploy or create GitHub Release objects."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
REMOTE = 'git@github.com:multitek-indo/PM.git'
SEMVER = re.compile(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)')


def git(*args, check=True):
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env['GIT_TERMINAL_PROMPT'] = '0'
    result = subprocess.run(['git', '-C', str(ROOT), *args], env=env,
                            text=True, capture_output=True, timeout=180)
    if check and result.returncode:
        # Never display the SSH command, keys or full Git environment.
        raise RuntimeError('Git '+args[0]+' gagal; periksa akses/kondisi repository. Tidak ada force push.')
    return result.returncode, result.stdout.strip()


def check_version(root=ROOT):
    version = (root/'app/VERSION.txt').read_text(encoding='utf-8').strip()
    if not SEMVER.fullmatch(version):
        raise ValueError('Isi app/VERSION.txt harus MAJOR.MINOR.PATCH, tanpa huruf v.')
    notes = root/'docs/releases'/f'{version}.md'
    if not notes.is_file() or len(notes.read_text().strip()) < 80:
        raise ValueError('Lengkapi catatan rilis di docs/releases/'+version+'.md (minimal 80 karakter).')
    return version


def remote_ref(ref):
    out = git('ls-remote', '--refs', 'origin', ref)[1]
    if not out:
        return None
    rows = out.splitlines()
    if len(rows) != 1:
        raise RuntimeError('Respons ref GitHub tidak tunggal.')
    oid, returned_ref = rows[0].split()
    if returned_ref != ref or not re.fullmatch('[a-f0-9]{40,64}', oid):
        raise RuntimeError('Respons GitHub tidak sesuai.')
    return oid


def tag_release():
    version = check_version()
    if ROOT == Path('/opt/multitek-pm') or git('rev-parse','--show-toplevel')[1] != str(ROOT):
        raise RuntimeError('Gunakan checkout development, bukan direktori produksi.')
    if git('branch','--show-current')[1] != 'main':
        raise RuntimeError('Rilis hanya dari branch main yang sudah direview.')
    if git('status','--porcelain=v1','--untracked-files=all')[1]:
        raise RuntimeError('Working tree belum bersih; commit/review perubahan dahulu.')
    for args in [('remote','get-url','--all','origin'),('remote','get-url','--push','--all','origin')]:
        if git(*args)[1] != REMOTE:
            raise RuntimeError('Tujuan harus multitek-indo/PM; konfigurasi tidak diganti.')
    head = git('rev-parse','HEAD')[1]
    if remote_ref('refs/heads/main') != head:
        raise RuntimeError('Main lokal dan GitHub berbeda. Sinkronkan tanpa force push.')
    ref = 'refs/tags/v'+version
    there = remote_ref(ref)
    if there is not None:
        if there == head:
            print('Tag v'+version+' sudah tersedia pada commit ini. Tidak ditulis ulang.')
            return
        raise RuntimeError('Versi sudah dipakai commit lain. Naikkan nomor versi; jangan pindahkan tag.')
    # Do not publish a version older than a stable numeric tag already on GitHub.
    refs = git('ls-remote','--tags','--refs','origin','refs/tags/v*')[1]
    versions = []
    for row in refs.splitlines():
        tail = row.split()[1].removeprefix('refs/tags/v')
        if SEMVER.fullmatch(tail):
            versions.append(tuple(map(int,tail.split('.'))))
    if versions and tuple(map(int,version.split('.'))) <= max(versions):
        raise RuntimeError('Versi harus lebih tinggi dari tag numerik yang sudah dirilis.')
    rc, local = git('rev-parse','--verify',ref,check=False)
    if rc == 0 and local != head:
        raise RuntimeError('Tag lokal berbeda; tidak menimpa tag lokal.')
    guard = ROOT/'tools/git_safety.py'
    if not guard.is_file():
        raise RuntimeError('Guard keamanan Git tidak ditemukan.')
    subprocess.run([sys.executable,str(guard),'--stage'],cwd=ROOT,check=True)
    if rc:
        git('tag','v'+version,head)
    git('push','origin',ref)
    if remote_ref(ref) != head:
        raise RuntimeError('Push sudah dicoba, tetapi hasil belum dapat diverifikasi. Jangan force push.')
    print('PASS TAG: v'+version+' -> '+head)
    print('Lanjutkan di GitHub > Releases > Draft a new release; pilih tag yang sudah ada.')
    print('Tag dan GitHub Release tidak mengubah aplikasi yang sedang berjalan di VPS.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['check','tag'])
    args = parser.parse_args()
    try:
        if args.action == 'check':
            print('PASS VERSION: '+check_version())
        else:
            tag_release()
        return 0
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as exc:
        print('STOP RELEASE: '+str(exc),file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
