#!/usr/bin/env bash
# Multitek PM - reproducible FRESH VPS installation from a clean GitHub checkout.
# Source: https://github.com/multitek-indo/PM
# Usage: sudo bash ops/install-vps.sh --domain pm.example.com
#        sudo bash ops/install-vps.sh --check --domain pm.example.com
#        sudo bash ops/install-vps.sh --local-only
# Does not migrate another server's data, modify cloudflared/DNS, or touch other Compose projects.
set -Eeuo pipefail
umask 077

APP=/opt/multitek-pm
PROJECT=multitek-pm
PORT=18080
MODE=install
DOMAIN=''
STAGE=''
STARTED_DB=0

say() { printf '\n[PM] %s\n' "$*"; }
stop() { printf '\nSTOP PM: %s\n' "$*" >&2; exit 1; }
usage() {
  cat <<'EOF'
Multitek PM - installer VPS baru
  sudo bash ops/install-vps.sh --check --domain pm.example.com
  sudo bash ops/install-vps.sh --domain pm.example.com
  sudo bash ops/install-vps.sh --local-only

Prerequisites: Ubuntu Linux, Git clone multitek-indo/PM, Docker Engine 28+, Docker
Compose plugin, >=3.2 GiB memory, >=1.8 GiB MemAvailable, >=30 GiB disk free.
Cloudflared/DNS/Cloudflare Access must be configured separately on the correct VPS.
For initial install only. Never run against an existing /opt/multitek-pm.
EOF
}
while (( $# )); do
  case "$1" in
    --check) MODE=check; shift ;;
    --install) MODE=install; shift ;;
    --local-only) [[ -z "$DOMAIN" ]] || stop '--local-only tidak boleh bersama --domain'; DOMAIN=''; shift ;;
    --domain) [[ $# -ge 2 ]] || stop '--domain memerlukan hostname'; DOMAIN="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) stop "Argumen tidak dikenali: $1" ;;
  esac
done
[[ "$(id -u)" -eq 0 ]] || stop 'Jalankan sebagai root dengan sudo.'
for cmd in git docker python3 ss curl flock tar stat readlink; do
  command -v "$cmd" >/dev/null 2>&1 || stop "$cmd tidak tersedia. Siapkan prasyarat dulu."
done

if [[ -n "$DOMAIN" ]]; then
  python3 - "$DOMAIN" <<'PY'
import ipaddress,re,sys
s=sys.argv[1]
if len(s)>253 or '.' not in s or s!=s.lower() or s.endswith('.'):
    raise SystemExit('STOP: Domain harus FQDN huruf kecil, tanpa https:// atau path.')
for part in s.split('.'):
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',part):
        raise SystemExit('STOP: Label domain tidak valid.')
try:
    ipaddress.ip_address(s)
except ValueError:
    pass
else:
    raise SystemExit('STOP: Masukkan hostname DNS, bukan IP.')
PY
fi

[[ -z "${DOCKER_HOST:-}" ]] || stop 'DOCKER_HOST remote tidak diizinkan.'
ctx="$(docker context show)"
endpoint="$(docker context inspect "$ctx" --format '{{.Endpoints.docker.Host}}' 2>/dev/null)"
[[ "$endpoint" == unix://* ]] || stop 'Docker context harus socket lokal VPS.'
docker info >/dev/null 2>&1 || stop 'Docker Engine tidak aktif.'
docker compose version >/dev/null 2>&1 || stop 'Docker Compose plugin tidak tersedia.'
engine="$(docker version --format '{{.Server.Version}}')"
major="${engine%%.*}"
[[ "$major" =~ ^[0-9]+$ && "$major" -ge 28 ]] || stop 'Docker Engine 28+ diperlukan untuk binding loopback.'

# Installer must come from the tracked repository, not from a renamed external payload.
SELF="$(readlink -f "${BASH_SOURCE[0]}")"
SOURCE_ROOT="$(dirname "$(dirname "$SELF")")"
[[ "$SELF" == "$SOURCE_ROOT/ops/install-vps.sh" ]] || stop 'Jalankan dari ops/install-vps.sh dalam repository.'
[[ "$SOURCE_ROOT" != "$APP" ]] || stop 'Jangan jalankan installer fresh dari source produksi.'
git -C "$SOURCE_ROOT" rev-parse --is-inside-work-tree | grep -qx true || stop 'Bukan clone Git.'
TOP="$(git -C "$SOURCE_ROOT" rev-parse --show-toplevel)"
[[ "$TOP" == "$SOURCE_ROOT" ]] || stop 'Installer tidak berada di root clone.'
remote="$(git -C "$SOURCE_ROOT" remote get-url origin)"
case "$remote" in
  https://github.com/multitek-indo/PM|https://github.com/multitek-indo/PM.git|git@github.com:multitek-indo/PM.git)
    ;;
  *) stop 'Git origin bukan multitek-indo/PM; periksa repository.' ;;
esac
git -C "$SOURCE_ROOT" ls-files --error-unmatch ops/install-vps.sh >/dev/null 2>&1 || stop 'Installer harus sudah menjadi file Git yang dipush ke repository.'
[[ -z "$(git -C "$SOURCE_ROOT" status --porcelain --untracked-files=no)" ]] || stop 'Source tracked belum clean. Review perubahan lalu gunakan commit/release.'
COMMIT="$(git -C "$SOURCE_ROOT" rev-parse HEAD)"
[[ "$COMMIT" =~ ^[a-f0-9]{40}$ ]] || stop 'Commit checkout tidak valid.'
for file in compose.yaml requirements.txt pmctl app/manage.py app/config/settings.py app/config/test_settings.py app/maintenance/management/commands/pm_bootstrap.py db-init/10-pm-role.sh; do
  [[ -f "$SOURCE_ROOT/$file" && ! -L "$SOURCE_ROOT/$file" ]] || stop "Source wajib hilang atau symlink: $file"
done
if [[ -n "$DOMAIN" ]]; then
  for setting in SECURE_PROXY_SSL_HEADER SECURE_SSL_REDIRECT SECURE_REDIRECT_EXEMPT; do
    grep -Fq "$setting" "$SOURCE_ROOT/app/config/settings.py" || stop "Source belum mendukung HTTPS origin: $setting"
  done
fi
for rel in .env private sparepart_uploads; do
  if git -C "$SOURCE_ROOT" ls-files --error-unmatch "$rel" >/dev/null 2>&1 || git -C "$SOURCE_ROOT" ls-files "$rel/" | grep -q .; then
    stop "Repo melacak path runtime/secret: $rel"
  fi
done

# Only fresh installs. Existing PM sources, volumes and containers are never touched.
[[ ! -e "$APP" && ! -L "$APP" ]] || stop "$APP sudah ada. Ini hanya fresh install; jangan menimpa data."
[[ -z "$(docker ps -aq --filter label=com.docker.compose.project=$PROJECT)" ]] || stop 'Kontainer Docker PM sudah ada.'
if docker volume ls --format '{{.Name}}' | grep -Eq '^multitek-pm_'; then
  stop 'Volume PM lama terdeteksi. Jangan hapus data; gunakan prosedur recovery.'
fi
if docker network ls --format '{{.Name}}' | grep -Eq '^multitek-pm_'; then
  stop 'Network PM lama terdeteksi. Jangan mengubahnya.'
fi
[[ -z "$(ss -H -ltn "( sport = :$PORT )")" ]] || stop "Port $PORT sudah dipakai. Tidak menghentikan service lain."

python3 - <<'PY'
from pathlib import Path
import shutil
ram={line.split(':',1)[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith(('MemTotal:','MemAvailable:'))}
total=ram.get('MemTotal',0);available=ram.get('MemAvailable',0)
free=shutil.disk_usage('/opt').free
print('RAM: total %.2f GiB, available %.2f GiB | Disk free: %.1f GiB' %(total/1024**3,available/1024**3,free/1024**3))
if total < 3.2*1024**3: raise SystemExit('STOP: RAM total <3.2 GiB. Naikkan alokasi VM lebih dulu.')
if available < 1.8*1024**3: raise SystemExit('STOP: MemAvailable <1.8 GiB; terlalu berisiko untuk service lain.')
if free < 30*1024**3: raise SystemExit('STOP: Ruang /opt <30 GiB; perlu kapasitas aman.')
PY
say "Preflight lulus. Git commit: $COMMIT"
if [[ "$MODE" == check ]]; then
  printf 'PASS CHECK: fresh source dan Docker siap. Tidak ada perubahan dibuat.\n'
  printf 'Instal: sudo bash ops/install-vps.sh %s\n' "${DOMAIN:+--domain $DOMAIN}"
  exit 0
fi

exec 9>/run/lock/multitek-pm-fresh-install.lock
flock -n 9 || stop 'Operasi instalasi PM lain sedang berjalan.'
# Re-check critical collision after taking installer lock.
[[ ! -e "$APP" ]] || stop "$APP muncul selama pemeriksaan."
[[ -z "$(docker ps -aq --filter label=com.docker.compose.project=$PROJECT)" ]] || stop 'Ada project PM lain setelah pemeriksaan.'
OLD_RUNNING="$(docker ps --format '{{.Names}}')"

on_error() {
  local code=$? line="$1"
  trap - ERR
  printf '\nINSTALL STOP (exit=%s, baris=%s).\n' "$code" "$line" >&2
  printf 'Staging: %s\n' "${STAGE:-tidak ada}" >&2
  printf 'Source runtime: %s\n' "$APP" >&2
  printf 'Jangan hapus pgdata atau ulang bootstrap tanpa audit bila PM sudah pernah start.\n' >&2
  exit "$code"
}
trap 'on_error "$LINENO"' ERR

say 'Mengambil snapshot source dari COMMIT yang sudah di-clone (git archive).'
STAGE="$(mktemp -d /opt/.multitek-pm-new.XXXXXXXX)"
ROOT="$STAGE/source"
mkdir "$ROOT"
git -C "$SOURCE_ROOT" archive --format=tar "$COMMIT" | tar -xf - -C "$ROOT"
# All code must be regular files; restore permissions for non-root Django/postgres.
python3 - "$ROOT" <<'PY'
from pathlib import Path
import os,stat,sys
root=Path(sys.argv[1]); dirs=[]; files=[]
for parent,ns,fs in os.walk(root,followlinks=False):
    dirs.append(Path(parent))
    for name in ns:
        p=Path(parent)/name
        if not stat.S_ISDIR(os.lstat(p).st_mode):
            raise SystemExit('STOP: Source directory symlink/special: '+str(p))
    for name in fs:
        p=Path(parent)/name
        s=os.lstat(p)
        if not stat.S_ISREG(s.st_mode) or s.st_size>20*1024*1024:
            raise SystemExit('STOP: Source file symlink/special/large: '+str(p))
        files.append((p,bool(s.st_mode&0o111)))
    if len(dirs)+len(files)>10000:
        raise SystemExit('STOP: Source archive terlalu besar.')
for d in dirs: os.chmod(d,0o755)
for f,executable in files: os.chmod(f,0o755 if executable else 0o644)
print('PASS source permission: %d folder, %d file; code bisa dibaca UID 10001 dan PostgreSQL.'%(len(dirs),len(files)))
PY
for req in compose.yaml requirements.txt app/manage.py db-init/10-pm-role.sh ops/install-vps.sh; do
  [[ -f "$ROOT/$req" ]] || stop "Snapshot tidak lengkap: $req"
done

say 'Memakai image resmi Python dan PostgreSQL dengan digest immutable untuk instalasi ini.'
docker pull python:3.12-slim-bookworm
docker pull postgres:16
export PM_PYTHON_IMAGE="$(docker image inspect -f '{{.Id}}' python:3.12-slim-bookworm)"
export PM_POSTGRES_IMAGE="$(docker image inspect -f '{{.Id}}' postgres:16)"
export ROOT DOMAIN COMMIT
mkdir -m 0700 "$ROOT/private" "$ROOT/reports" "$ROOT/sparepart_uploads"
chown 10001:10001 "$ROOT/sparepart_uploads"
python3 - <<'PY'
from pathlib import Path
import os,secrets
p=Path(os.environ['ROOT']); domain=os.environ['DOMAIN']
admin=secrets.token_urlsafe(30)
config={
 'PM_PYTHON_IMAGE':os.environ['PM_PYTHON_IMAGE'],
 'PM_POSTGRES_IMAGE':os.environ['PM_POSTGRES_IMAGE'],
 'PM_SECRET_KEY':secrets.token_urlsafe(64),
 'PM_DB_PASSWORD':secrets.token_urlsafe(42),
 'PM_POSTGRES_PASSWORD':secrets.token_urlsafe(42),
 'PM_ALLOWED_HOSTS':(domain+',' if domain else '')+'127.0.0.1,localhost',
 'PM_PUBLIC_BASE_URL':'https://'+domain if domain else '',
 'PM_CSRF_ORIGINS':'https://'+domain if domain else '',
 'PM_HTTPS':'1' if domain else '0',
}
files={
 p/'.env':''.join(k+'='+v+'\n' for k,v in config.items()),
 p/'private/bootstrap.env':'PM_ADMIN_PASSWORD='+admin+'\n',
 p/'private/login.txt':(
  'Multitek PM - password awal. JANGAN unggah file ini ke GitHub.\n'
  'Username: admin\nPassword: '+admin+'\n'
  'Git commit: '+os.environ['COMMIT']+'\n'
  'Origin host: http://127.0.0.1:18080\n'
  'Hostname: '+('https://'+domain if domain else '(local-only)')+'\n'
 ),
}
for f,body in files.items():
    with f.open('x',encoding='utf-8') as out: out.write(body)
    f.chmod(0o600)
print('PASS: secret dan admin baru dibuat; file private 0600. Nilai tidak dicetak.')
PY
unset PM_PYTHON_IMAGE PM_POSTGRES_IMAGE PM_SECRET_KEY PM_DB_PASSWORD PM_POSTGRES_PASSWORD PM_ALLOWED_HOSTS PM_PUBLIC_BASE_URL PM_CSRF_ORIGINS PM_HTTPS PM_ADMIN_PASSWORD
unset COMPOSE_FILE COMPOSE_PROJECT_NAME COMPOSE_PROFILES COMPOSE_ENV_FILES COMPOSE_DISABLE_ENV_FILE || true

compose_stage() { docker compose --project-directory "$ROOT" -p "$PROJECT" -f "$ROOT/compose.yaml" --env-file "$ROOT/.env" "$@"; }
validate_compose() {
  local root="$1"
  docker compose --project-directory "$root" -p "$PROJECT" -f "$root/compose.yaml" --env-file "$root/.env" --profile tools config --format json | python3 -c '
import json,sys
root=sys.argv[1];obj=json.load(sys.stdin);s=obj.get("services",{})
assert obj.get("name")=="multitek-pm", "Compose project berubah"
assert {"web","scheduler","db","setup","bootstrap"}.issubset(s), "Service wajib tidak lengkap (perlu --profile tools)"
assert set(s["setup"].get("profiles",[]))=={"tools"} and set(s["bootstrap"].get("profiles",[]))=={"tools"}, "Profile setup/bootstrap berbeda"
ports=s["web"].get("ports",[])
assert len(ports)==1 and ports[0].get("host_ip")=="127.0.0.1" and str(ports[0].get("published"))=="18080" and int(ports[0].get("target",0))==8000, "Web port bukan loopback 18080"
assert not s["db"].get("ports") and not s["scheduler"].get("ports"), "DB/scheduler mempunyai port host"
assert {"pgdata","packages"}.issubset(obj.get("volumes",{})), "Volume yang diperlukan berubah"
assert any(v.get("source")==root+"/db-init" and v.get("target")=="/docker-entrypoint-initdb.d" and v.get("type")=="bind" and v.get("read_only") for v in s["db"].get("volumes",[])), "DB init mount tidak sesuai"
for k,svc in s.items():
    assert svc.get("network_mode")!="host", "Host networking tidak boleh dipakai"
    for v in svc.get("volumes",[]):
        if v.get("type")=="bind":
            assert str(v.get("source","")).startswith(root+"/"), "Bind mount di luar folder PM: "+k
print("PASS Compose: services, profiles, initdb mount, localhost:18080, volume isolasi.")
' "$root"
}

say 'Validasi Compose termasuk profile tools; tidak mencetak konfigurasi atau password.'
validate_compose "$ROOT"

say 'Instal dependencies dan jalankan Django checks + test dari SQLite sementara.'
compose_stage --profile tools run --rm --no-deps setup

say 'Mengaktifkan direktori source produksi, tanpa menimpa service lain.'
[[ ! -e "$APP" ]] || stop 'Direktori target muncul tiba-tiba; stop tanpa overwrite.'
mv "$ROOT" "$APP"
rmdir "$STAGE" 2>/dev/null || true
STAGE=''
compose() { docker compose --project-directory "$APP" -p "$PROJECT" -f "$APP/compose.yaml" --env-file "$APP/.env" "$@"; }
validate_compose "$APP"

say 'Start PostgreSQL PM dengan volume baru; tunggu healthy (hingga 3 menit).'
compose up -d db
DB_ID="$(compose ps -q db)"
[[ -n "$DB_ID" ]] || stop 'Container database PM tidak terbentuk.'
ready=0
for i in $(seq 1 90); do
  s="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$DB_ID" 2>/dev/null || true)"
  if [[ "$s" == healthy ]]; then ready=1;break;fi
  if (( i % 10 == 0 )); then echo "Waiting DB health ($i/90): ${s:-unknown}";fi
  sleep 2
done
[[ "$ready" -eq 1 ]] || stop 'PostgreSQL belum healthy. Periksa permission db-init dan docker logs. Jangan hapus pgdata.'

# A single bootstrap only: guard against a partially initialized database.
state="$(docker exec -i "$DB_ID" sh -ec 'export PGPASSWORD="$POSTGRES_PASSWORD"; exec psql -X -A -t -v ON_ERROR_STOP=1 -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
SELECT (SELECT count(*) FROM pg_roles WHERE rolname='pm_app')::text || ',' ||
       (SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tablename='django_migrations')::text;
SQL
)" || stop 'Tidak bisa memverifikasi skema PostgreSQL sebelum bootstrap.'
[[ "$state" == '1,0' ]] || stop "Bootstrap diblokir: state role/migrations=$state (expected 1,0). Review sebelum lanjut."

say 'Migrasi PostgreSQL PM baru, buat grup/role dan admin awal, init scheduler.'
compose --profile tools run --rm --no-deps bootstrap

say 'Start hanya web dan scheduler project Multitek PM.'
compose up -d --no-deps web scheduler
login_host="${DOMAIN:-localhost}"
forwarded='http'
[[ -z "$DOMAIN" ]] || forwarded='https'
status='000'; health='000'
for i in $(seq 1 45); do
  health="$(curl --noproxy '*' -sS -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:18080/healthz 2>/dev/null || true)"
  status="$(curl --noproxy '*' -sS -o /dev/null -w '%{http_code}' --max-time 5 -H "Host: $login_host" -H "X-Forwarded-Proto: $forwarded" http://127.0.0.1:18080/login/ 2>/dev/null || true)"
  if [[ "$health" == 200 && "$status" == 200 ]]; then break;fi
  sleep 2
done
[[ "$health" == 200 && "$status" == 200 ]] || stop "Web gagal verifikasi (health=$health login=$status); lihat docker logs web PM."
if [[ -n "$DOMAIN" ]]; then
  compose exec -T web python -c '
import os,sys
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
from django.conf import settings as s
domain=sys.argv[1]
assert domain in s.ALLOWED_HOSTS and "https://"+domain in s.CSRF_TRUSTED_ORIGINS
assert s.PUBLIC_BASE_URL=="https://"+domain
assert s.SECURE_PROXY_SSL_HEADER==("HTTP_X_FORWARDED_PROTO","https")
assert s.SESSION_COOKIE_SECURE and s.CSRF_COOKIE_SECURE and s.SECURE_SSL_REDIRECT
print("PASS Django: domain, trusted proxy, Secure cookies, HTTPS redirect.")
' "$DOMAIN"
fi
for cname in multitek-pm-db-1 multitek-pm-web-1 multitek-pm-scheduler-1; do
  [[ "$(docker inspect -f '{{.State.Running}}' "$cname" 2>/dev/null || true)" == true ]] || stop "Container $cname tidak berjalan."
done
while IFS= read -r old; do
  [[ -n "$old" ]] || continue
  [[ "$(docker inspect -f '{{.State.Running}}' "$old" 2>/dev/null || true)" == true ]] || stop "Container sebelumnya berhenti: $old"
done <<< "$OLD_RUNNING"

say 'SUKSES: Multitek PM siap di host localhost:18080.'
compose ps
printf '\nSource commit: %s\n' "$COMMIT"
printf 'Akun admin: sudo cat /opt/multitek-pm/private/login.txt (JANGAN bagikan password).\n'
if [[ -n "$DOMAIN" ]]; then
  printf 'Cloudflare hostname: https://%s\n' "$DOMAIN"
  printf 'Pasang route pada tunnel di VPS INI: HTTP -> http://127.0.0.1:18080\n'
  printf 'Pastikan Cloudflare Access dan DNS aktif. Installer TIDAK mengubah tunnel atau DNS.\n'
else
  printf 'Mode local-only: gunakan SSH forwarding untuk login tanpa hostname publik.\n'
fi
printf 'Belum sertifikasi production. Validasi role, stok, stock opname, backup dan restore.\n'
