import os
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ['PM_SECRET_KEY']
DEBUG = False
ALLOWED_HOSTS = [x.strip() for x in os.environ.get('PM_ALLOWED_HOSTS', '127.0.0.1,localhost').split(',') if x.strip()]
PUBLIC_BASE_URL = os.environ.get('PM_PUBLIC_BASE_URL', '').rstrip('/')
CSRF_TRUSTED_ORIGINS = [x.strip() for x in os.environ.get('PM_CSRF_ORIGINS', '').split(',') if x.strip()]
INSTALLED_APPS = ['django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles', 'maintenance']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'whitenoise.middleware.WhiteNoiseMiddleware', 'django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware', 'django.contrib.messages.middleware.MessageMiddleware', 'django.middleware.clickjacking.XFrameOptionsMiddleware']
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND':'django.template.backends.django.DjangoTemplates', 'DIRS':[BASE_DIR/'templates'], 'APP_DIRS':True, 'OPTIONS':{'context_processors':['django.template.context_processors.request', 'django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION = 'config.wsgi.application'
DATABASES = {'default': {'ENGINE':'django.db.backends.postgresql', 'NAME':'multitek_pm', 'USER':'pm_app', 'PASSWORD':os.environ.get('PM_DB_PASSWORD', ''), 'HOST':'db', 'PORT':'5432', 'CONN_MAX_AGE':60, 'OPTIONS':{'connect_timeout':10, 'options':'-c statement_timeout=20000 -c lock_timeout=5000'}}}
LANGUAGE_CODE = 'id'
TIME_ZONE = 'Asia/Jakarta'
USE_I18N = True
USE_TZ = True
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR/'staticfiles'
STATICFILES_DIRS = [BASE_DIR/'static']
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = False
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_PASSWORD_VALIDATORS = [{'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'}, {'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS':{'min_length':12}}, {'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'}, {'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'}]
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 8*3600
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
# Private pilot uses HTTP over an encrypted SSH tunnel. No public route is created.
SESSION_COOKIE_SECURE = os.environ.get('PM_HTTPS', '0') == '1'
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
SECURE_SSL_REDIRECT = False
DATA_UPLOAD_MAX_MEMORY_SIZE = 2*1024*1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2*1024*1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000

# BEGIN MULTITEK PM CLOUDFLARE HTTPS v1
# Trust this header only while the origin remains private and the trusted
# Cloudflare proxy overwrites X-Forwarded-Proto. Do not publish port 18080.
if SESSION_COOKIE_SECURE:
    from urllib.parse import urlsplit as _pm_urlsplit
    _pm_origin = _pm_urlsplit(PUBLIC_BASE_URL)
    if (_pm_origin.scheme != 'https' or not _pm_origin.hostname
            or _pm_origin.username or _pm_origin.password
            or _pm_origin.port or _pm_origin.query or _pm_origin.fragment
            or _pm_origin.path not in ('', '/')):
        raise ValueError('PM_PUBLIC_BASE_URL harus origin HTTPS tanpa path/port.')
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SECURE_SSL_HOST = _pm_origin.hostname
    # Docker checks this endpoint over loopback HTTP; it only runs SELECT 1.
    SECURE_REDIRECT_EXEMPT = [r'^healthz$']
# END MULTITEK PM CLOUDFLARE HTTPS v1

# BEGIN PM VERSION AND COMPANY IDENTITY 0.3
# Existing database, network, security, clock and maintenance settings stay intact.
from .version import APP_VERSION
INSTALLED_APPS = [*INSTALLED_APPS, 'branding.apps.BrandingConfig']
TEMPLATES[0]['OPTIONS']['context_processors'].append('branding.context_processors.company_identity')
# END PM VERSION AND COMPANY IDENTITY 0.3

# BEGIN SPAREPART PHOTO 0.3.1
INSTALLED_APPS.append('spareparts.apps.SparepartsConfig')
SPAREPART_STORAGE_DIR = '/var/pm-spareparts'
# END SPAREPART PHOTO 0.3.1
