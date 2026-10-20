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
