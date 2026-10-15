# 01 - Arsitektur dan pemisahan lingkungan

[Kembali ke indeks](README.md)

## 1. Komponen yang tersedia

| Lapisan | Implementasi dalam source | Tanggung jawab |
|---|---|---|
| Web | Django 5.2, Gunicorn, template HTML | Login, halaman, form, dan izin |
| Tampilan | `app/templates/`, `app/static/pm.css` | HTML server-side, tata letak responsif |
| Data | PostgreSQL 16 pada produksi | Mesin, jadwal, work order, audit, dan pengguna |
| Penjadwalan | `python manage.py pm_scheduler` | Memanggil generator, jeda 300 detik |
| Runtime | Docker Compose project `multitek-pm` | Container web, scheduler, dan database |
| Static | WhiteNoise | Menyajikan CSS dari source static |
| QR | Paket `qrcode`, keluaran SVG | Tautan HTTPS ke detail mesin; tetap memerlukan login |
| Riwayat kode | Git dan GitHub | Commit, branch, review, dokumentasi |

Tidak ada React, Vue, Celery, Redis untuk antrean PM, n8n, atau API REST umum
pada baseline ini. Redis milik Nextcloud bukan komponen aplikasi PM.
Lihat [Compose](../../compose.yaml), [requirements](../../requirements.txt),
dan [settings](../../app/config/settings.py).

## 2. Jalur permintaan

```text
Browser -> Cloudflare Access (bila dikonfigurasi) -> Cloudflare Tunnel
        -> 127.0.0.1:18080 pada VPS -> web:8000 -> Django -> PostgreSQL db:5432

Scheduler PM -> services.generate_orders() -> PostgreSQL PM yang sama
Tailscale SSH -> administrasi VPS; bukan login aplikasi PM
```

Akses privat awal juga dapat memakai SSH local forwarding. Setelah patch HTTPS
aktif, login HTTP lokal dapat diarahkan ke hostname HTTPS. Status akhir DNS,
Cloudflare Access, dan hostname harus diverifikasi pada akun pengguna; panduan
ini tidak menyatakan konfigurasi publik sudah berhasil hanya dari source code.

## 3. Resource dan data

| Service | Batas memori / CPU pada Compose | Penyimpanan dan port |
|---|---|---|
| `web` | 768 MiB / 0,75 vCPU | Source `/app` read-only; host `127.0.0.1:18080` |
| `scheduler` | 256 MiB / 0,25 vCPU | Source dan package read-only; tanpa published port |
| `db` | 512 MiB / 0,50 vCPU | `multitek-pm_pgdata`; tanpa published port |
| `setup` | 512 MiB / 0,50 vCPU | Service profil tools, mengisi volume package |
| `bootstrap` | 512 MiB / 0,50 vCPU | Migrasi/bootstrap awal; bukan rutin deployment |

Network: `multitek-pm_pm`. Package Python runtime: `multitek-pm_packages`.
Database: `multitek_pm`; pengguna aplikasi: `pm_app`; pemilik awal: `pm_owner`.
Kredensial runtime ada di `.env` privat VPS, bukan di GitHub.

Volume terpisah tidak memisahkan disk fisik: PM, Nextcloud, Odoo, dan layanan lain
masih berbagi host. Jangan menganggap CPU/memori yang dibatasi menjamin tidak ada
kompetisi I/O. `restart: unless-stopped` juga bukan high availability.

## 4. Tiga lingkungan yang harus dibedakan

**Produksi** memakai `/opt/multitek-pm`, database PM sebenarnya, port 18080,
dan data lapangan. Jangan melakukan eksperimen, git checkout, atau instal ulang
baseline di direktori ini.

**Development** memakai checkout Git. Virtual environment dan SQLite dev
terpisah dapat digunakan untuk latihan UI; konfigurasi contohnya ada di
[examples/dev_settings.py](examples/dev_settings.py). Server development hanya
bind ke `127.0.0.1:18081` dan tidak dipublikasikan lewat Cloudflare.

**Staging** belum disediakan sebagai deployment siap pakai. Sebelum rilis yang
mengubah data/concurrency, buat lingkungan PostgreSQL terpisah dengan nama
project, port, volume, user, dan kredensial sendiri. Mengganti lokasi folder saja
tidak cukup; Compose produksi memiliki nama project yang sama.

## 5. Variabel yang boleh dikonfigurasi, bukan ditanam ke kode

| Nama | Fungsi | Perlakuan |
|---|---|---|
| `PM_SECRET_KEY` | Penandatanganan keamanan Django | Rahasia; jangan commit; perubahan dapat membatalkan sesi |
| `PM_DB_PASSWORD` | Password akun aplikasi PM | Rahasia; jangan ubah tanpa sinkronisasi database |
| `PM_POSTGRES_PASSWORD` | Password pemilik PostgreSQL saat inisialisasi | Rahasia; bukan cara otomatis merotasi password volume lama |
| `PM_ALLOWED_HOSTS` | Hostname yang boleh diterima | Daftar host, bukan `*` |
| `PM_PUBLIC_BASE_URL` | Origin HTTPS untuk QR | Domain final, tanpa path/query |
| `PM_CSRF_ORIGINS` | Origin HTTPS formulir yang dipercaya | Harus sesuai domain yang dipakai browser |
| `PM_HTTPS` | Mode cookie HTTPS dan, jika patch ada, trusted proxy | `1` untuk konfigurasi HTTPS yang telah diverifikasi |
| `PM_PYTHON_IMAGE`, `PM_POSTGRES_IMAGE` | Image yang dipakai Compose | Perubahan memerlukan evaluasi versi dan deployment |

File `.env.example` hanya contoh nama variabel. Jangan menyalin nilai `.env`
produksi ke contoh tersebut. Patch HTTPS terletak di akhir `settings.py` dengan
penanda `BEGIN MULTITEK PM CLOUDFLARE HTTPS v1`; jangan hilangkan ketika memperbarui
kode dari ZIP baseline lama.
