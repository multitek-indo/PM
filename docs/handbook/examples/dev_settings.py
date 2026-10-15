"""Development-only settings, never install as production settings.

Usage from repository root:
  export PYTHONPATH="$PWD/docs/handbook/examples:$PWD/app"
  .venv/bin/python app/manage.py runserver 127.0.0.1:18081 --settings=dev_settings

Uses a private local DEV directory, SQLite, and an independent secret.
Does not read /opt/multitek-pm/.env or connect to production PostgreSQL.
"""
import os
import stat
from pathlib import Path

DEV_DIR = Path.home() / '.local' / 'share' / 'multitek-pm-dev'
if DEV_DIR.is_symlink():
    raise RuntimeError('Direktori DEV tidak boleh berupa symlink.')
DEV_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
if DEV_DIR.resolve() != DEV_DIR:
    raise RuntimeError('Path DEV melewati symlink; pilih lokasi dev terpisah.')
os.chmod(DEV_DIR, 0o700)
SECRET_FILE = DEV_DIR / 'django-secret.txt'
if not SECRET_FILE.exists():
    import secrets
    try:
        fd = os.open(SECRET_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(secrets.token_urlsafe(48))
if SECRET_FILE.is_symlink() or not SECRET_FILE.is_file():
    raise RuntimeError('File secret DEV tidak valid.')
if stat.S_IMODE(SECRET_FILE.stat().st_mode) & 0o077:
    raise RuntimeError('Secret DEV harus hanya dapat dibaca pemilik (mode 600).')
_dev_secret = SECRET_FILE.read_text(encoding='utf-8').strip()
if len(_dev_secret) < 32:
    raise RuntimeError('Secret DEV tidak valid; jangan memakai secret produksi.')
# Override inherited PM variables before importing production defaults.
os.environ['PM_SECRET_KEY'] = _dev_secret
os.environ['PM_HTTPS'] = '0'
os.environ['PM_PUBLIC_BASE_URL'] = ''
os.environ['PM_CSRF_ORIGINS'] = ''
os.environ['PM_ALLOWED_HOSTS'] = '127.0.0.1,localhost'
from config.settings import *  # noqa: E402,F401,F403

DEBUG = True
ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3',
                         'NAME': str(DEV_DIR / 'dev.sqlite3')}}
PUBLIC_BASE_URL = ''
CSRF_TRUSTED_ORIGINS = []
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
SECURE_PROXY_SSL_HEADER = None
SECURE_SSL_HOST = None
WHITENOISE_AUTOREFRESH = True
