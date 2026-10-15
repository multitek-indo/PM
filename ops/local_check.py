import json, sys, time, urllib.request
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
for attempt in range(60):
    try:
        data=json.loads(opener.open('http://127.0.0.1:18080/healthz',timeout=4).read())
        if data.get('service')!='multitek-pm' or data.get('status')!='ok':
            raise RuntimeError('Unexpected application response')
        login=opener.open('http://127.0.0.1:18080/login/',timeout=4).read()
        if b'Smart Maintenance' not in login: raise RuntimeError('Login not rendered')
        with opener.open('http://127.0.0.1:18080/static/pm.css',timeout=4) as r:
            if r.status!=200: raise RuntimeError('Static CSS not served')
        print('PASS: health database, halaman login dan stylesheet lokal merespons.')
        sys.exit(0)
    except Exception:
        time.sleep(2)
print('FAIL: aplikasi belum lolos pemeriksaan lokal. Periksa log project multitek-pm.',file=sys.stderr)
sys.exit(1)
