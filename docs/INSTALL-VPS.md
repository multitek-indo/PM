# Multitek Smart Maintenance - Fresh install VPS dari GitHub

Installer ini untuk VPS BARU dan DATABASE KOSONG. Source GitHub tidak berisi data dari VPS lain.

## Prasyarat

- Ubuntu Linux x86_64, akses `sudo`/root.
- Docker Engine 28+ dan Docker Compose plugin sudah terinstal dan aktif.
- Git, Python 3, curl, tar, ss (`iproute2`), flock (`util-linux`).
- RAM guest minimal 3.2 GiB, MemAvailable minimal 1.8 GiB, ruang kosong `/opt` minimal 30 GiB.
- Port host `127.0.0.1:18080` bebas.
- Repositori `multitek-indo/PM` dapat di-clone (akses SSH GitHub jika repo privat).
- Backup/snapshot host jika VPS sudah memuat service lain. Installer tidak mematikan service lain.

Instalasi tidak mengubah partisi/LVM atau otomatis memasang Docker, karena berisiko
untuk host yang memiliki service produksi lain. Perluas disk/upgrade RAM terlebih dulu bila dibutuhkan.

## Satu perintah instalasi setelah clone

Pada VPS baru:

```bash
git clone https://github.com/multitek-indo/PM.git
cd PM
sudo bash ops/install-vps.sh --domain pm-baru.multitekindo.com
```

Ganti `pm-baru.multitekindo.com` dengan hostname yang ingin dipakai. Jangan gunakan
hostname yang sudah dipakai tunnel/server lain tanpa migrasi terencana.

Untuk preflight tanpa perubahan:

```bash
sudo bash ops/install-vps.sh --check --domain pm-baru.multitekindo.com
```

Untuk fresh install **tanpa** domain HTTPS (hanya SSH forwarding):

```bash
sudo bash ops/install-vps.sh --local-only
```

Tiga tahap inti installer: preflight isolasi -> Git archive commit aktif, images &
file private -> Django setup/test -> PostgreSQL baru -> bootstrap SEKALI -> web dan scheduler.

## Cloudflare Zero Trust

Aplikasi memakai `127.0.0.1:18080` di VPS. Database tidak dibuka ke host.
Saat instalasi memakai `--domain`, Django menerima hostname, origin CSRF, dan
trusted HTTPS proxy dari awal. Cookie CSRF/sesi diatur Secure; healthcheck tetap
bisa dijalankan melalui HTTP loopback.

1. Pastikan `cloudflared` terpasang dan berjalan di **host Ubuntu VPS yang sama**,
   atau gunakan setup container dengan network namespace yang memang dapat menjangkau
   origin `127.0.0.1` pada host. Jika cloudflared ada di server lain, localhost
   merujuk server lain itu, bukan VPS aplikasi.
2. Di Cloudflare Zero Trust buat/pilih tunnel untuk VPS tersebut.
3. Tambahkan **Published application route**: hostname `pm-baru.multitekindo.com`,
   `Service Type: HTTP`, `Service URL: http://127.0.0.1:18080`.
4. Periksa record DNS hostname di zona yang otoritatif; dashboard biasanya
   membuat CNAME ketika route dibuat. Jangan membuat record duplikat.
5. Lindungi hostname menggunakan **Cloudflare Access (Self-hosted)**; batasi
   pengguna yang boleh login. Jangan mengandalkan halaman login Django sebagai
   satu-satunya perlindungan untuk aplikasi yang belum diaudit produksi.

Installer **tidak membuat tunnel, DNS, token, maupun Access Policy otomatis**.
Agar semua langkah itu otomatis, diperlukan alur autentikasi Cloudflare terpisah
beserta otorisasi pemilik zona. Jangan simpan token tunnel atau API di repo.

## Login dan verifikasi

Saat installer sukses:

```bash
sudo cat /opt/multitek-pm/private/login.txt
curl -i http://127.0.0.1:18080/healthz
sudo /opt/multitek-pm/pmctl status
```

Username awal: `admin`. Password selalu berbeda pada setiap instalasi; tidak ada
password universal. Jangan kirim isi `login.txt`, `.env` atau backup ke chat/repo.

Jika domain belum disetel dan mengakses dari PC, gunakan SSH forwarding:

```bash
ssh -N -L 127.0.0.1:18081:127.0.0.1:18080 USER@IP_VPS
```

Browser pada PC: `http://127.0.0.1:18081`.

## Perlindungan data dan perubahan berikutnya

- Instalasi fresh akan **STOP** jika `/opt/multitek-pm`, volume, container,
  network `multitek-pm`, atau port 18080 sudah ada. Tidak melakukan overwrite.
- Jangan menjalankan `docker compose down -v`, `docker system prune`, atau
  menghapus volume PostgreSQL untuk mencoba ulang pemasangan parsial.
- Jika terjadi error setelah migrasi, jangan ulang `bootstrap` sembarangan;
  periksa status tabel `django_migrations` dan audit transaksi terlebih dahulu.
- `.env`, login.txt, bootstrap.env, database dan file foto dibuat **di VPS**,
  bukan di GitHub.
- `git pull` pada checkout kode **tidak otomatis** memperbarui server produksi.
  Pembaruan versi memerlukan backup, pengujian migrasi, deploy versi tertentu,
  healthcheck, dan rollback plan yang terpisah.
- Keberhasilan instalasi hanya membuktikan aplikasi dapat berjalan. Sebelum
  operasional resmi, verifikasi role, flow PM, stok, stock opname, ledger,
  keamanan, dan restore backup.

## Menambahkan installer ke GitHub (sekali untuk pengembang)

Letakkan file `ops/install-vps.sh` dan `docs/INSTALL-VPS.md` di checkout kerja
Git yang terpisah dari `/opt/multitek-pm`, lalu:

```bash
git add ops/install-vps.sh docs/INSTALL-VPS.md
git diff --cached --check
git diff --cached --stat
git commit -m "feat: reproducible fresh VPS installer"
git push origin main
```

Jalankan review sebelum commit. Jangan force push. Jika branch `main` dilindungi,
gunakan Pull Request. Push ini tidak menginstal apa pun pada VPS secara otomatis.

# Multitek PM -- Fresh VPS Auto Installer v2

Sumber repository: `https://github.com/multitek-indo/PM`.

## Fungsi

Installer `ops/install-vps.sh` untuk **fresh install** pada Ubuntu/Debian 64-bit
mengatur perangkat lunak yang diperlukan tanpa menimpa project Docker yang ada.
Tidak berlaku sebagai updater instalasi PM yang sudah ada.

- Memeriksa RAM minimal 3,2 GiB total, 1,8 GiB tersedia, dan disk kosong 30 GiB.
- Memasang tools host yang tidak tersedia melalui APT dengan simulasi yang menolak
  penghapusan/pembaruan paket existing.
- Jika Docker CLI+Engine ada: gunakan apa adanya; aktifkan daemon apabila sedang mati,
  tanpa restart daemon yang aktif.
- Jika Docker tidak ada sama sekali: pasang Docker resmi dari APT vendor dengan
  verifikasi fingerprint kunci; jangan menghapus paket Docker lain.
- Jika Docker Compose tidak ada: coba paket Compose yang aman dahulu, lalu plugin
  resmi `v5.6.0` dengan SHA-256 yang dipin. **Tidak mengganti Docker Engine**.
- Clone dibuat oleh operator; installer mengunci source pada Git commit HEAD.
- Memasang Django dependencies, menjalankan tes setup, membuat PostgreSQL PM
  dalam volume baru, membuat role, migrasi, akun admin, scheduler dan web.
- Origin HTTP hanya di `127.0.0.1:18080`; PostgreSQL tidak dipublikasikan.
- Saat `--domain` dipakai, Django `ALLOWED_HOSTS`, CSRF, Secure cookies dan
  proxy HTTPS disesuaikan dari awal.
- Default admin pada instalasi BARU: **username `admin`, password `admin123`**.
  Middleware mewajibkan administrator mengganti password melalui `/password/`
  sebelum dapat membuka dashboard (minimal 12 karakter melalui password validator).

## Persiapan repository (satu kali saja oleh pemelihara proyek)

Masukkan file paket ini ke **checkout kerja Git terpisah**, BUKAN `/opt/multitek-pm`
pada VPS produksi. Setelah file ditaruh sesuai relative path:

```bash
python3 ops/enable-first-login.py
bash -n ops/install-vps.sh
python3 -m py_compile ops/enable-first-login.py app/config/first_login.py app/maintenance/test_first_login_password.py

git diff --check
git status --short
git add ops/install-vps.sh ops/enable-first-login.py \
  app/config/first_login.py app/config/settings.py \
  app/maintenance/test_first_login_password.py docs/INSTALL-VPS.md
git commit -m "feat: automated fresh VPS installer and first-login password rotation"
git push origin main
```

Jangan force-push. Jika repository telah berubah, periksa diff dan merge lebih dulu.
`git push` hanya mengunggah source; tidak otomatis men-deploy ke server lain.

## Instalasi VPS baru (setelah pembaruan GitHub tersedia)

Ubuntu/Debian minimal memerlukan Git untuk melakukan clone:

```bash
sudo apt-get update
sudo apt-get install -y git

git clone https://github.com/multitek-indo/PM.git
cd PM
sudo bash ops/install-vps.sh --domain nama-host.multitekindo.com
```

Jika server sudah mempunyai Git, jalankan 3 perintah terakhir. **Jangan gunakan
`--check` sebagai tahap wajib di server tanpa Docker Compose**: `--check` sengaja
read-only dan akan melaporkan tool yang belum ada. Jalankan pemasangan langsung
`--domain` agar dependensi disiapkan otomatis.

Mode lain:

```bash
sudo bash ops/install-vps.sh --check --domain nama-host.multitekindo.com
sudo bash ops/install-vps.sh --local-only
```

Hasil pemasangan:

- Source runtime: `/opt/multitek-pm` (terpisah dari checkout Git).
- Origin HTTP: `http://127.0.0.1:18080`.
- Username/password pertama: `admin` / `admin123` (wajib diganti saat login).
- File kredensial lokal: `/opt/multitek-pm/private/login.txt` (mode 0600).
- Container PM: `multitek-pm-web-1`, `multitek-pm-db-1`, `multitek-pm-scheduler-1`.

Verifikasi:

```bash
docker ps --filter label=com.docker.compose.project=multitek-pm
curl --noproxy '*' -fsS http://127.0.0.1:18080/healthz
```

## Cloudflare Tunnel (tetap dikonfigurasi terpisah)

Jika `cloudflared` berjalan secara native pada **host VPS yang sama**, buat route
pada tunnel Cloudflare Zero Trust:

- Hostname: `nama-host.multitekindo.com`.
- Service Type: HTTP.
- Service URL: `http://127.0.0.1:18080`.
- Pastikan CNAME/proxied DNS tersambung ke tunnel dan Cloudflare Access hanya
  mengizinkan administrator atau identitas yang ditunjuk.

**PENTING:** password `admin123` dikenal secara publik. Buat Cloudflare Access
sebelum membuat route publik; ganti password pada sesi login pertama segera.
Kewajiban mengganti password tidak mencegah orang lain login lebih dulu jika
origin dipublikasikan tanpa Access. Installer **tidak** memasang/mengubah tunnel,
Access policy, token, atau DNS.

Jika cloudflared berjalan di container atau mesin lain, alamat `127.0.0.1`
merujuk ke network namespace/container tersebut, bukan otomatis ke VPS PM.
Atur akses jaringan private yang benar; jangan memublikasikan port 18080 ke WAN.

## Penanganan kegagalan

- Installer menolak instalasi jika `/opt/multitek-pm`, project/container, volume,
  network PM, atau port 18080 sudah ada.
- Setelah membuat database, installer **tidak** mencoba reset/rollback volume.
  Jika gagal, simpan state dan log; gunakan diagnosis/recovery khusus, bukan
  rerun fresh installer atau `docker compose down -v`.
- Installer tidak mengubah data, volume, container, atau database Collabora,
  Odoo, Mekanik Bot, Helix, maupun aplikasi Docker lain.
- Jika perlu migrasi data dari VPS lama, gunakan backup+restore PostgreSQL dan
  upload terencana secara terpisah.

## Batas verifikasi

File paket telah diperiksa dengan Bash `-n`, AST Python, fixture middleware dan
simulasi patch settings. Pengujian di Docker/PostgreSQL VPS baru belum dilakukan.
Jangan gunakan sebagai sertifikasi keamanan atau kesiapan data produksi.

