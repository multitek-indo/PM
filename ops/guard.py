"""Read-only baseline of existing services. Never reads passwords or configuration."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

def run(args,timeout=30):
    label = ' '.join(args[:3])
    try:
        p = subprocess.run(args, text=True, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f'Pemeriksaan timeout {timeout}s: {label}') from exc
    if p.returncode:
        detail = ' '.join(p.stderr.split())[:800] or '(stderr kosong)'
        raise RuntimeError(f'Pemeriksaan gagal: {label}; exit={p.returncode}; {detail}')
    return p.stdout.strip()

def state_container(cid):
    # Do not request .Id: typed Docker responses expose ID, JSON exposes Id.
    # Do not dereference optional .State.Health in a Go template.
    # Read only state/identity, not Config.Env or the complete inspect output.
    fmt = '{{.Name}}|{{.RestartCount}}|{{json .State}}'
    raw = run(['docker','inspect','--type','container','--format',fmt,cid])
    try:
        name, restarts, state_json = raw.split('|', 2)
        state = json.loads(state_json)
        if not isinstance(state, dict):
            raise ValueError('State bukan object')
        if not isinstance(state.get('Running'), bool):
            raise ValueError('Running tidak valid')
        if not isinstance(state.get('StartedAt'), str) or not state['StartedAt']:
            raise ValueError('StartedAt tidak valid')
        if not name.startswith('/') or not restarts.isdigit():
            raise ValueError('Identitas atau RestartCount tidak valid')
        health_obj = state.get('Health')
        if health_obj is None:
            health = 'none'
        elif isinstance(health_obj, dict) and health_obj.get('Status') in ('healthy','unhealthy','starting'):
            health = health_obj['Status']
        else:
            raise ValueError('Health tidak valid')
        if any(state.get(k, False) for k in ('Paused','Restarting','Dead')):
            raise ValueError('Container paused/restarting/dead')
        running = 'true' if state['Running'] else 'false'
    except (ValueError, TypeError, KeyError) as exc:
        raise RuntimeError('Status container tidak valid: '+cid[:12]+'; '+str(exc)) from exc
    return '|'.join((cid, name, running, state['StartedAt'], str(int(restarts)), health))

def nextcloud_status():
    executable=shutil.which('nextcloud.occ') or '/snap/bin/nextcloud.occ'
    raw=run([executable,'status'],timeout=45)
    fields={}
    for line in raw.splitlines():
        match=re.match(r'\s*-\s*(installed|maintenance|needsDbUpgrade|version):\s*(.*)',line)
        if match: fields[match.group(1)]=match.group(2).strip()
    if fields.get('installed')!='true' or fields.get('maintenance')!='false' or fields.get('needsDbUpgrade')!='false':
        raise RuntimeError('Nextcloud tidak dalam status aplikasi yang diharapkan.')
    return fields

def baseline():
    ids=run(['docker','ps','-q','--no-trunc']).splitlines()
    if not ids: raise RuntimeError('Tidak menemukan container produksi yang diharapkan.')
    containers={cid:state_container(cid) for cid in ids}
    for cid,s in containers.items():
        if '|true|' not in s or s.endswith('|unhealthy'):
            raise RuntimeError('Container produksi tidak sehat sebelum instalasi.')
    units=['cloudflared.service','tailscaled.service','snap.nextcloud.apache.service','snap.nextcloud.mysql.service','snap.nextcloud.php-fpm.service','snap.nextcloud.redis-server.service','snap.nextcloud.nextcloud-cron.service']
    states={}
    for unit in units:
        active=run(['systemctl','is-active',unit])
        if active!='active': raise RuntimeError(unit+' tidak aktif.')
        states[unit]=run(['systemctl','show',unit,'--property=ActiveEnterTimestampMonotonic','--value'])
    return {'containers':containers,'units':states,'nextcloud':nextcloud_status()}

def compare(before):
    problems=[]
    for cid,old in before['containers'].items():
        try:
            current=state_container(cid)
            if current!=old: problems.append('State/start/restart/health container berubah: '+old.split('|')[1])
        except Exception: problems.append('Container lama tidak dapat diperiksa: '+cid[:12])
    for unit,stamp in before['units'].items():
        try:
            if run(['systemctl','is-active',unit])!='active': problems.append(unit+' tidak aktif.')
            if run(['systemctl','show',unit,'--property=ActiveEnterTimestampMonotonic','--value'])!=stamp:
                problems.append(unit+' mengalami pergantian waktu mulai.')
        except Exception: problems.append('Gagal membaca '+unit)
    try:
        if nextcloud_status()!=before['nextcloud']: problems.append('Status aplikasi Nextcloud berubah.')
    except Exception: problems.append('Status aplikasi Nextcloud gagal diverifikasi.')
    if problems: raise RuntimeError('\n'.join(problems))
    print('PASS: seluruh container lama dan service inti tetap aktif; start/restart tidak berubah.')

if __name__=='__main__':
    try:
        mode,path=sys.argv[1:3]
        if mode=='save':
            Path(path).write_text(json.dumps(baseline(),indent=2))
            print('Baseline layanan lama tersimpan tanpa membaca kredensial.')
        elif mode=='check': compare(json.loads(Path(path).read_text()))
        else: raise RuntimeError('Mode guard tidak dikenal.')
    except Exception as exc:
        print('GUARD FAILED: '+str(exc),file=sys.stderr); sys.exit(1)
