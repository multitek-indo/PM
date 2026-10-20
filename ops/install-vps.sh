#!/usr/bin/env bash
# Multitek PM - reproducible FRESH VPS installation from a clean GitHub checkout.
# Source: https://github.com/multitek-indo/PM
# Usage: sudo bash ops/install-vps.sh --domain pm.example.com
#        sudo bash ops/install-vps.sh --check --domain pm.example.com
#        sudo bash ops/install-vps.sh --local-only
# Auto-provisions missing host prerequisites, without upgrading existing Docker Engine.
# On fresh installation only: admin/admin123, must rotate at first login.
# Does not migrate another server's data, modify cloudflared/DNS, or touch other Compose projects.
set -Eeuo pipefail
umask 077

APP=/opt/multitek-pm
PROJECT=multitek-pm
PORT=18080
MODE=install
DOMAIN=''
LOCAL_ONLY=0
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

Supported OS: Ubuntu or Debian, apt-get, systemd, Git clone multitek-indo/PM.
--install: installs missing host CLI tools and Docker Compose plugin automatically.
If Docker is absent, installs official Docker Engine from Docker's APT repository.
Existing Docker Engine will NEVER be upgraded, removed, or restarted.
--check is read-only: reports missing dependencies, never installs packages.
Requires Docker Engine 28+, >=3.2 GiB RAM, >=1.8 GiB MemAvailable, >=30 GiB free.
Initial admin login: admin / admin123 (enforced password change on first login).
Cloudflared tunnel, DNS and Cloudflare Access require separate authorization.
Fresh install only. Never run against an existing /opt/multitek-pm.
EOF
}
while (( $# )); do
  case "$1" in
    --check) MODE=check; shift ;;
    --install) MODE=install; shift ;;
    --local-only) [[ -z "$DOMAIN" ]] || stop '--local-only tidak boleh bersama --domain'; LOCAL_ONLY=1; DOMAIN=''; shift ;;
    --domain) [[ $# -ge 2 ]] || stop '--domain memerlukan hostname'; [[ "$LOCAL_ONLY" -eq 0 ]] || stop '--domain tidak boleh bersama --local-only'; DOMAIN="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) stop "Argumen tidak dikenali: $1" ;;
  esac
done
[[ "$(id -u)" -eq 0 ]] || stop 'Jalankan sebagai root dengan sudo.'
# Do not run APT or touch Docker if PM is already installed.
[[ ! -e "$APP" && ! -L "$APP" ]] || stop "$APP already exists; fresh install refuses to overwrite it."

[[ -z "${DOCKER_HOST:-}" ]] || stop 'Remote DOCKER_HOST is not allowed.'
[[ -z "${DOCKER_CONTEXT:-}" ]] || stop 'DOCKER_CONTEXT override is not allowed.'

if [[ -r /etc/os-release ]]; then
  . /etc/os-release
else
  stop '/etc/os-release is missing.'
fi
case "${ID:-}" in
  ubuntu|debian) ;;
  *) stop 'Automatic prerequisites support Ubuntu/Debian only; use a supported VPS.' ;;
esac
command -v apt-get >/dev/null 2>&1 || stop 'apt-get is required for automatic prerequisites.'
command -v systemctl >/dev/null 2>&1 || stop 'systemd is required for automatic Docker daemon management.'

# Fail before installing/starting any Docker prerequisite on an undersized VPS.
# This fast preflight uses standard host files and does not modify disk/RAM.
[[ -d /opt && -r /proc/meminfo ]] || stop 'Host /opt or /proc/meminfo is not available.'
mem_total_kb="$(awk '$1=="MemTotal:" {print $2}' /proc/meminfo)"
mem_avail_kb="$(awk '$1=="MemAvailable:" {print $2}' /proc/meminfo)"
disk_free_kb="$(df -Pk /opt | awk 'NR==2 {print $4}')"
[[ "$mem_total_kb" =~ ^[0-9]+$ && "$mem_avail_kb" =~ ^[0-9]+$ && "$disk_free_kb" =~ ^[0-9]+$ ]] || stop 'Failed to read host resource limits.'
printf '[PM] Preflight before APT: RAM total %s MiB; available %s MiB; disk free %s GiB.\n' \
  "$((mem_total_kb/1024))" "$((mem_avail_kb/1024))" "$((disk_free_kb/1024/1024))"
(( mem_total_kb >= 3355444 )) || stop 'RAM total less than 3.2 GiB. Do not install on this VPS yet.'
(( mem_avail_kb >= 1887437 )) || stop 'MemAvailable less than 1.8 GiB. Existing services need more memory.'
(( disk_free_kb >= 31457280 )) || stop 'Free space less than 30 GiB. Expand disk first.'

# A pre-existing flock is used early; on bare hosts apt/dpkg has its own lock.
if [[ "$MODE" != check ]]; then
  exec 8>/run/lock/multitek-pm-deps-install.lock
  if command -v flock >/dev/null 2>&1; then
    flock -n 8 || stop 'Another Multitek PM prerequisites operation is running.'
  fi
fi

# APT simulation must never remove or upgrade existing installed packages.
apt_safe_install() {
  (( $# > 0 )) || return 0
  local sim
  sim="$(DEBIAN_FRONTEND=noninteractive apt-get -s -o DPkg::Lock::Timeout=30 install --no-install-recommends "$@")" || stop "APT cannot safely resolve: $*"
  if grep -Eq '^Remv |^Inst [^ ]+ \[' <<< "$sim"; then
    stop "APT plans removal or upgrade of installed packages. Review manually: $*"
  fi
  DEBIAN_FRONTEND=noninteractive apt-get -y -o DPkg::Lock::Timeout=30 install --no-install-recommends "$@"
}

install_cli_dependencies() {
  local packages=() item cmd pkg
  for item in 'git:git' 'python3:python3' 'ss:iproute2' 'curl:curl' \
              'tar:tar' 'stat:coreutils' 'readlink:coreutils' 'sha256sum:coreutils' \
              'flock:util-linux' 'mktemp:coreutils' 'install:coreutils'; do
    cmd="${item%%:*}";pkg="${item#*:}"
    if ! command -v "$cmd" >/dev/null 2>&1; then
      packages+=("$pkg")
    fi
  done
  if (( ${#packages[@]} )); then
    if [[ "$MODE" == check ]]; then
      stop "Missing host tools (${packages[*]}). --install can install them; --check never modifies the host."
    fi
    say "Installing missing host tools: ${packages[*]}"
    apt-get update -qq
    # Deduplicate package names (coreutils etc.) while preserving order.
    local unique=() known p
    for p in "${packages[@]}"; do
      known=0
      for old in "${unique[@]}"; do [[ "$p" != "$old" ]] || known=1; done
      (( known )) || unique+=("$p")
    done
    apt_safe_install "${unique[@]}"
  fi
}

install_official_docker_engine() {
  [[ "$MODE" != check ]] || stop 'Docker CLI missing; --install can install Docker Engine, --check is read-only.'
  # Never replace an existing daemon, orphan an existing Docker data root, or
  # break third-party containers such as Collabora.
  if [[ -d /var/lib/docker || -S /var/run/docker.sock ]] || command -v dockerd >/dev/null 2>&1 || \
     dpkg-query -W -f='${Status}' docker.io docker-ce containerd.io 2>/dev/null | grep -q 'install ok installed'; then
    stop 'Existing Docker daemon/data/packages detected but docker CLI missing. Refusing reinstall.'
  fi
  say 'Docker is absent. Installing official Docker Engine (new host only).'
  local dist arch codename temp_file key_file source_file expected_fp got_fp
  dist="${ID}"
  arch="$(dpkg --print-architecture)"
  codename="${VERSION_CODENAME:-${UBUNTU_CODENAME:-}}"
  [[ "$arch" =~ ^(amd64|arm64)$ && "$codename" =~ ^[a-z]+$ ]] || stop 'Unsupported OS codename/architecture for Docker APT.'
  # Check repository release exists before writing host APT sources.
  curl -fsSI --retry 2 --connect-timeout 10 "https://download.docker.com/linux/$dist/dists/$codename/Release" >/dev/null || \
    stop "Official Docker APT repository not published for $dist/$codename. No Docker installation attempted."
  apt-get update -qq
  local extra=()
  command -v gpg >/dev/null 2>&1 || extra+=(gnupg)
  [[ -f /etc/ssl/certs/ca-certificates.crt ]] || extra+=(ca-certificates)
  (( ${#extra[@]} == 0 )) || apt_safe_install "${extra[@]}"
  key_file=/etc/apt/keyrings/docker.asc
  source_file=/etc/apt/sources.list.d/docker.sources
  if [[ -e "$source_file" || -L "$source_file" || -e "$key_file" || -L "$key_file" ]]; then
    stop 'Docker APT source/key already exists in unexpected state; refusing overwrite.'
  fi
  install -d -m 0755 /etc/apt/keyrings
  temp_file="$(mktemp)"
  curl -fsSL --retry 3 --connect-timeout 15 "https://download.docker.com/linux/$dist/gpg" -o "$temp_file"
  expected_fp='9DC858229FC7DD38854AE2D88D81803C0EBFCD88'
  got_fp="$(gpg --show-keys --with-colons "$temp_file" 2>/dev/null | awk -F: '$1=="fpr" {print $10;exit}')"
  [[ "$got_fp" == "$expected_fp" ]] || { rm -f "$temp_file"; stop 'Docker APT key fingerprint mismatch.'; }
  install -m 0644 "$temp_file" "$key_file"
  rm -f "$temp_file"
  cat > "$source_file" <<EOF
Types: deb
URIs: https://download.docker.com/linux/$dist
Suites: $codename
Components: stable
Architectures: $arch
Signed-By: $key_file
EOF
  chmod 0644 "$source_file"
  apt-get update -qq
  apt_safe_install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
  docker info >/dev/null 2>&1 || stop 'New Docker Engine did not start.'
  say 'Docker Engine and Compose installed and activated.'
}

ensure_docker_engine() {
  if ! command -v docker >/dev/null 2>&1; then
    install_official_docker_engine
  else
    local ctx endpoint engine major
    ctx="$(docker context show 2>/dev/null)" || stop 'Cannot read Docker context.'
    endpoint="$(docker context inspect "$ctx" --format '{{.Endpoints.docker.Host}}' 2>/dev/null)" || stop 'Cannot inspect Docker context.'
    [[ "$endpoint" == unix://* ]] || stop 'Docker context must be a local UNIX socket.'
    if ! docker info >/dev/null 2>&1; then
      [[ "$MODE" != check ]] || stop 'Docker daemon is stopped. --check will not start it.'
      say 'Docker installed but inactive. Starting existing daemon (no restart).'
      systemctl start docker || stop 'Failed to start existing Docker daemon.'
    fi
  fi
  local engine major ctx endpoint
  ctx="$(docker context show)"
  endpoint="$(docker context inspect "$ctx" --format '{{.Endpoints.docker.Host}}' 2>/dev/null)"
  [[ "$endpoint" == unix://* ]] || stop 'Docker context is not local.'
  docker info >/dev/null 2>&1 || stop 'Docker Engine unavailable.'
  engine="$(docker version --format '{{.Server.Version}}')"
  major="${engine%%.*}"
  [[ "$major" =~ ^[0-9]+$ && "$major" -ge 28 ]] || stop 'Docker Engine 28+ required. Existing Engine is NEVER auto-upgraded.'
}

ensure_compose_plugin() {
  docker compose version >/dev/null 2>&1 && { say "Compose ready: $(docker compose version --short)"; return 0; }
  [[ "$MODE" != check ]] || stop 'Docker Compose plugin is missing. --install can install it; --check is read-only.'
  say 'Compose plugin missing. Trying standalone CLI plugin package without changing Docker Engine.'
  local sim candidate plugin_pkg
  plugin_pkg=''
  for candidate in docker-compose-plugin docker-compose-v2; do
    if ! apt-cache policy "$candidate" 2>/dev/null | grep -Eq 'Candidate: [^ (][^ ]*'; then
      continue
    fi
    sim="$(apt-get -s install --no-install-recommends "$candidate" 2>/dev/null || true)"
    if [[ -n "$sim" ]] && ! grep -Eq '^Remv |^Inst (docker-ce |docker-ce-cli |docker.io |containerd.io |containerd |runc )|^Inst [^ ]+ \[' <<< "$sim"; then
      plugin_pkg="$candidate"
      break
    fi
  done
  if [[ -n "$plugin_pkg" ]]; then
    apt_safe_install "$plugin_pkg"
  fi
  if docker compose version >/dev/null 2>&1; then
    say "Compose plugin activated: $(docker compose version --short)"
    return 0
  fi
  # No compatible apt package: use an immutable, SHA-256 verified official
  # Docker Compose release. Never overwrite a pre-existing plugin binary.
  local asset digest arch dest tmp
  arch="$(uname -m)"
  case "$arch" in
    x86_64) asset=docker-compose-linux-x86_64; digest=40343e21ca777173e69cff5dbafeb37c6f81f3b0d57d9e597f036e95eb63e76a ;;
    aarch64) asset=docker-compose-linux-aarch64; digest=733ec76717ceb59052a9609bdadfb523b2df8eab57a54212872d10a58078ea2 ;;
    *) stop "No pinned Compose CLI plugin for architecture: $arch" ;;
  esac
  dest=/usr/local/lib/docker/cli-plugins/docker-compose
  [[ ! -e "$dest" && ! -L "$dest" ]] || stop "Compose plugin path already exists: $dest. Review before changing it."
  tmp="$(mktemp)"
  if ! curl -fSL --retry 3 --connect-timeout 20 --max-time 180 \
    "https://github.com/docker/compose/releases/download/v5.6.0/$asset" -o "$tmp"; then
    rm -f "$tmp"
    stop 'Failed to download official Docker Compose binary.'
  fi
  if ! printf '%s  %s\n' "$digest" "$tmp" | sha256sum -c - >/dev/null; then
    rm -f "$tmp"
    stop 'Compose binary SHA-256 verification failed.'
  fi
  install -d -m 0755 "$(dirname "$dest")"
  install -m 0755 "$tmp" "$dest"
  rm -f "$tmp"
  # Keep existing Docker Engine untouched. An invalid plugin can be removed
  # only when its exact newly installed path is still the one we own.
  if ! docker compose version >/dev/null 2>&1; then
    rm -f "$dest"
    stop 'Downloaded Compose plugin was not recognized; no Docker daemon restart performed.'
  fi
  say "Verified Compose plugin activated: $(docker compose version --short)"
}

install_cli_dependencies
if [[ "$MODE" != check ]]; then
  flock -n 8 || stop 'Another Multitek PM prerequisites operation is running.'
fi
ensure_docker_engine
ensure_compose_plugin
for cmd in git docker python3 ss curl flock tar stat readlink sha256sum; do
  command -v "$cmd" >/dev/null 2>&1 || stop "$cmd is still missing after prerequisites installation."
done

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
for file in compose.yaml requirements.txt pmctl app/manage.py app/config/settings.py app/config/test_settings.py app/config/first_login.py app/maintenance/test_first_login_password.py app/maintenance/management/commands/pm_bootstrap.py db-init/10-pm-role.sh; do
  [[ -f "$SOURCE_ROOT/$file" && ! -L "$SOURCE_ROOT/$file" ]] || stop "Source wajib hilang atau symlink: $file"
done
if [[ -n "$DOMAIN" ]]; then
  for setting in SECURE_PROXY_SSL_HEADER SECURE_SSL_REDIRECT SECURE_REDIRECT_EXEMPT; do
    grep -Fq "$setting" "$SOURCE_ROOT/app/config/settings.py" || stop "Source belum mendukung HTTPS origin: $setting"
  done
fi
grep -Fq 'config.first_login.EnforceInitialAdminPasswordChange' "$SOURCE_ROOT/app/config/settings.py" || stop 'First-login password rotation middleware belum diaktifkan; jalankan python3 ops/enable-first-login.py pada repo sebelum push.'
grep -Fq "path('password/'," "$SOURCE_ROOT/app/config/urls.py" || stop 'Rute ganti password Django tidak ditemukan.'
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
for req in compose.yaml requirements.txt app/manage.py app/config/first_login.py app/maintenance/test_first_login_password.py db-init/10-pm-role.sh ops/install-vps.sh; do
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
  'Multitek PM - temporary login for fresh VPS. DO NOT commit to GitHub.\n'
  'Username: admin\nPassword: '+admin+'\n'
  'Git commit: '+os.environ['COMMIT']+'\n'
  'Origin host: http://127.0.0.1:18080\n'
  'Hostname: '+('https://'+domain if domain else '(local-only)')+'\n'
  'WARNING: on first login immediately change the default password via /password/.\n'
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

say 'Set temporary default password for the newly created admin only.'
# Django bootstrap enforces a strong bootstrap password. Keep this security test;
# then set the explicitly requested short default after the new admin exists.
# Never touch existing users/databases: fresh role/migration guard above must pass.
compose --profile tools run --rm --no-deps bootstrap python manage.py shell -c '
import os
from django.contrib.auth import get_user_model
User = get_user_model()
qs = User.objects.filter(username="admin", is_superuser=True, is_staff=True)
assert qs.count() == 1, "Expected exactly one newly created superuser"
u = qs.get()
assert u.check_password(os.environ["PM_ADMIN_PASSWORD"]), "Bootstrap admin state unexpected"
u.set_password("admin123")
u.save(update_fields=["password"])
u.refresh_from_db()
assert u.check_password("admin123"), "Default admin password was not set"
from django.conf import settings
assert "config.first_login.EnforceInitialAdminPasswordChange" in settings.MIDDLEWARE, "First-login enforcement inactive"
print("PASS: admin default password set; first-login enforcement active")
'
# Synchronize private login note only after DB password has been updated.
python3 - "$APP/private/login.txt" <<'PY_ADMIN_DEFAULT'
from pathlib import Path
import sys
p=Path(sys.argv[1]);raw=p.read_text()
lines=raw.splitlines(keepends=True)
assert sum(x.startswith('Username: admin') for x in lines)==1
assert sum(x.startswith('Password: ') for x in lines)==1
result=''.join('Password: admin123\n' if x.startswith('Password: ') else x for x in lines)
p.write_text(result)
p.chmod(0o600)
print('PASS: root-only login.txt synchronized to requested first-login password')
PY_ADMIN_DEFAULT

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
printf 'First login: admin / admin123 (FORCED password change at /password/).\n'
printf 'Credential file: sudo cat /opt/multitek-pm/private/login.txt (do not share).\n'
if [[ -n "$DOMAIN" ]]; then
  printf 'Cloudflare hostname: https://%s\n' "$DOMAIN"
  printf 'Pasang route pada tunnel NATIVE VPS INI: HTTP -> http://127.0.0.1:18080\n'
  printf 'WAJIB: aktifkan Cloudflare Access sebelum memublikasikan password awal universal.\n'
  printf 'Installer TIDAK mengubah tunnel, token, DNS, atau Access.\n'
else
  printf 'Mode local-only: gunakan SSH forwarding untuk login tanpa hostname publik.\n'
fi
printf 'Belum sertifikasi production. Validasi role, stok, stock opname, backup dan restore.\n'
