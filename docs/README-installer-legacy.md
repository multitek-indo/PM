# Multitek Smart Maintenance 0.1 - pilot privat

## Cakupan

Aplikasi awal Django 5.2 LTS untuk master mesin, impor CSV, jadwal berbasis hari,
work order otomatis, checklist, pengiriman hasil oleh teknisi, verifikasi oleh
orang berbeda, ekspor CSV, dashboard, dan log aktivitas. Tidak ada data contoh
atau akun publik. PostgreSQL terpisah dari database Odoo dan Nextcloud.

Ini bukan CMMS produksi yang sudah diaudit. Kode ini belum diuji beban ribuan
pengguna, belum diintegrasikan sensor, dan tidak menggantikan SOP keselamatan.
Hasil PM dan persetujuan pemeriksaan TIDAK otomatis berarti mesin aman/layak
operasi atau seluruh temuan kerusakan telah diperbaiki.

## Instalasi

Gunakan file `multitek-pm-v0.1-install.sh` yang menyertakan seluruh source.
Target spesifik: host `multitekoffice`, Docker lokal, Engine 28+, Docker Compose
plugin, Python3 host, serta container `odoo-cafe-db-1` berbasis PostgreSQL 16.
Docker 28+ disyaratkan untuk perlindungan published port localhost sesuai
peringatan Docker untuk versi lama. Installer TIDAK meng-upgrade Docker.

Unduh file installer ke PC, salin melalui SCP/Tailscale lalu jalankan dengan Bash
sebagai root. Tidak perlu menyalin heredoc panjang. Jangan mengeksekusi ulang pada
folder yang sudah ada. Skrip menolak menimpa `/opt/multitek-pm`, volume, network,
atau container project dengan nama yang sama.

Pemeriksaan prasyarat dan baseline, instalasi paket Python dalam container
terbatas, tes SQLite terisolasi, pembuatan database PM, migrasi, dan verifikasi
layanan lama dilakukan dalam satu eksekusi. Tidak ada apt upgrade, docker prune,
perubahan partisi, akses SQL langsung ke database lama, edit Cloudflare, atau restart host.

Installer memakai image PostgreSQL 16 yang sudah ada dengan ID image immutable,
BUKAN container, koneksi, password atau volume PostgreSQL Odoo. Python image
`python:3.12-slim-bookworm` diunduh bila belum ada dan dipatok ke image ID untuk
instalasi ini. Dependensi Python diambil dari PyPI; akses internet diperlukan.
Versi paket yang benar-benar terpasang disimpan pada volume packages di
`/packages/installed-versions.json`. Evaluasi security update tetap diperlukan.

## Lokasi dan isolasi

- Project: multitek-pm.
- Source: /opt/multitek-pm/app (bind read-only pada container).
- Data PostgreSQL: volume multitek-pm_pgdata, tidak memakai volume lama.
- Python dependencies: volume multitek-pm_packages, read-only pada runtime.
- Network baru: multitek-pm_pm; tidak join network Odoo atau Nextcloud.
- Web: host 127.0.0.1:18080 -> container port 8000.
- Database dan scheduler: tanpa published host port.
- Akun database aplikasi pm_app bukan superuser PostgreSQL.
- Web/scheduler: UID 10001 non-root, root filesystem read-only, semua capability
  dilepas, no-new-privileges, tmpfs untuk temporary files.
- Web 768 MiB / 0.75 vCPU; DB 512 MiB / 0.50; scheduler 256 MiB / 0.25.
- Jumlah batas runtime utama: 1536 MiB dan 1.50 vCPU. Bukan alokasi minimum tetap
  dan bukan jaminan beban puncak. Kernel/Docker/temporary buffers memiliki overhead.
- Setup dan bootstrap berjalan bergantian dengan batas 512 MiB / 0.50 vCPU.
- Log Docker: rotasi 10 MiB, 3 file per container.

Volume terpisah bukan disk fisik terpisah. Semua masih berbagi filesystem root,
CPU, memori, I/O dan storage Proxmox. Installer tidak memverifikasi kapasitas
fisik datastore Proxmox, dan tidak dapat menjamin nol gangguan.

## Akses privat

Dari CMD Windows yang tersambung Tailscale:

```
ssh -o ExitOnForwardFailure=yes -L 127.0.0.1:18080:127.0.0.1:18080 root@100.123.222.1
```

Jangan tutup sesi tersebut saat dashboard digunakan. Pada shell server:

```
cat /opt/multitek-pm/private/login.txt
```

Buka `http://127.0.0.1:18080` di browser PC yang menjalankan SSH forwarding.
Username admin; password acak dari file. Ganti password sesudah login pertama.
Jangan mengirim password, .env, atau folder private ke percakapan/repository.

Mode HTTP ini hanya untuk pilot melalui SSH terenkripsi. Port tidak dibuka ke
semua interface. Cloudflared dan Tailscale tidak dikonfigurasi ulang.

## Alur uji pertama

1. Masuk sebagai admin. Buka Administrasi > Pengguna; buat akun teknisi dengan
   password kuat berbeda. Akun teknisi tidak perlu Staff status atau Superuser.
   Masukkan ke grup Teknisi PM agar label perannya jelas.
2. Tambahkan 3-5 mesin uji dengan kode `TEST-...` atau impor CSV dari template
   kosong pada menu Master mesin > Impor CSV. Delimiter koma; encoding UTF-8.
   Labeli data percobaan dan jangan campur dengan laporan resmi.
3. Buat jadwal PM dari Administrasi. Pilih mesin dan teknisi, isi judul, interval
   hari, jatuh tempo, dan 1-30 baris checklist sesuai SOP. Tidak ada interval
   rekomendasi universal. Jangan melakukan pengukuran pada mesin berenergi
   tanpa prosedur/kualifikasi/peralatan yang sesuai.
4. Scheduler memeriksa tiap 5 menit dan membuat work order untuk tanggal jatuh
   tempo sampai 7 hari ke depan. Dashboard menampilkan heartbeat terakhir.
5. Login sebagai teknisi, buka work order sendiri, isi semua pemeriksaan,
   tambahkan catatan bila ada temuan tidak normal, kirim untuk verifikasi.
6. Login kembali sebagai admin/supervisor berbeda, setujui atau kembalikan
   pekerjaan. Pengguna yang mengisi tidak dapat menyetujui pekerjaan sendiri.

Bila satu orang menguji sendiri, buat dua akun uji berbeda. Untuk penggunaan
nyata, akun harus mewakili orang sebenarnya; dua akun satu orang bukan kontrol
pemisahan tugas yang efektif.

Supervisor tambahan: tambahkan pengguna ke grup Supervisor PM. Untuk mengelola
master melalui Django admin, aktifkan Staff status. Jangan berikan Superuser
pada semua teknisi. Hanya superuser yang mengelola akun pengguna pada pilot ini.

## Aturan penjadwalan dan laporan

- Basis kalender tetap (tanggal berikutnya = tanggal jatuh tempo + interval),
  BUKAN tanggal aktual pekerjaan selesai. Ini menjaga keterlambatan terlihat.
- Scheduler menyimpan UNIQUE(plan, due_date) dan row lock PostgreSQL untuk
  mencegah work order identik saat generator diulang.
- Maksimal 12 kejadian backlog per jadwal per putaran; sisanya tidak dibuang dan
  diproses pada putaran selanjutnya. Jangan memasukkan ribuan tanggal awal
  bertahun-tahun lampau tanpa evaluasi beban dan kebutuhan riwayat.
- Checklist disalin saat work order dibuat agar perubahan template tidak
  mengganti daftar pemeriksaan yang sudah pernah dijadwalkan.
- Menonaktifkan mesin/jadwal menghentikan pekerjaan baru, tidak menghapus sejarah.
- Mengubah teknisi master jadwal berlaku untuk pekerjaan yang belum dibuat.
  Work order terbuka dapat dialihkan supervisor melalui halaman work order.
- Status: open -> review -> done, atau review -> open ketika dikembalikan.
- Persetujuan tidak menghapus temuan gagal. Tindak lanjut corrective maintenance
  terstruktur belum tersedia dalam versi ini.
- KPI PM tepat waktu: WO jatuh tempo dari awal bulan sampai hari ini; pembilang
  harus sudah disetujui dan dikirim teknisi paling lambat tanggal jatuh tempo.
  Jadwal masa depan tidak masuk penyebut. KPI ini bukan MTBF/MTTR atau OEE.
- Ekspor CSV dibatasi 20.000 WO terbaru dari seluruh status, bukan filter layar.
- Impor dibatasi 5.000 mesin / 2 MB; atomik, tidak memperbarui kode yang sudah ada.
- User teknisi melihat WO yang ditugaskan kepadanya, tetapi master mesin masih
  dapat dibaca seluruh pengguna terdaftar. BELUM ada isolasi tenant/pabrik.

## QR, publikasi dan batas pilot

Endpoint QR SVG sudah disediakan, tetapi ditolak sampai PM_PUBLIC_BASE_URL
berisi origin HTTPS final yang valid. Label QR tidak dibuat dari localhost.
URL QR tetap perlu login; kode UUID bukan pengganti autentikasi.

Installer TIDAK mengubah Cloudflare Tunnel, DNS, Access policy, TLS, SSH atau
firewall host yang sudah ada. Docker akan membuat network dan aturan publikasi
untuk project baru seperti operasi Docker biasa.

Sebelum publikasi, diperlukan hostname final, autentikasi perimeter (misalnya
Cloudflare Access), evaluasi hak akses, perlindungan percobaan login berulang,
konfigurasi HTTPS/cookie/CSRF/ALLOWED_HOSTS dan trusted proxy yang benar,
pengujian pada HP, serta backup dan uji restore. Jangan hanya membuat route
publik sambil mempertahankan konfigurasi pilot HTTP privat.

Tidak tersedia: upload foto/video, IoT, perhitungan jam operasi sensor, Telegram/
WhatsApp/email, stok spare part, offline mode, approval berjenjang, isolasi
multi-tenant, high availability, atau log kebal manipulasi admin server.

## Operasi project baru

```
bash /opt/multitek-pm/pmctl status
bash /opt/multitek-pm/pmctl logs
bash /opt/multitek-pm/pmctl stop
bash /opt/multitek-pm/pmctl start
```

Perintah stop hanya menghentikan project PM. Tidak menghapus data atau volume.
Bila instalasi gagal sesudah konfigurasi PM dibuat, error handler mencoba
menghentikan HANYA project PM baru. Data baru dan laporan tetap dipertahankan.
Baca `reports/install.log`; jangan kirim file rahasia. Jangan menjalankan
`docker compose down -v`, `docker volume prune`, atau `docker system prune`.

## Backup

Belum dibuat dan tidak dijalankan, sesuai urutan pekerjaan yang diminta.
Baseline layanan dan log installer BUKAN backup data. Tetapkan backup database
PM, source/config terenkripsi, file aplikasi, serta backup Odoo/Nextcloud dan VM
pada tahap berikut. Uji restore sebelum aplikasi menjadi acuan operasional.
Direktori lain pada root yang sama, termasuk bind mount /mnt/port3, tidak memberi
perlindungan terhadap kegagalan disk/VM yang sama.

## Verifikasi yang tersedia

Di lingkungan pembuatan paket: sintaks Python/Bash, parsing YAML, pemeriksaan
struktur isolasi, dan tiga uji fungsi penjadwalan murni dilakukan. Runtime Docker,
Django dan PostgreSQL tidak tersedia / dependensi tidak berhasil diunduh di
lingkungan pembuatan ini, sehingga hasil tes integrasi BELUM diklaim lulus.

Saat dijalankan di VPS, installer terlebih dahulu menjalankan Django checks,
model/migration drift check dan 33 tes fungsi pada SQLite in-memory di container
setup yang dibatasi resource. Tes mencakup jadwal, duplikasi, akses, checklist,
verifikasi, CSV dan rendering halaman. Hanya setelah lulus, database PostgreSQL
PM dibuat. Migrasi database PostgreSQL baru dan health endpoint kemudian diuji;
ini BUKAN pengujian beban atau concurrency PostgreSQL menyeluruh.

Guard membandingkan container ID, status, start time, restart count, health,
status unit systemd dan status OCC Nextcloud sebelum/sesudah. Ini tidak
membuktikan semua data lama utuh atau semua jalur penggunaan aplikasi lama
sudah diuji end-to-end.

## Referensi teknis (diakses 15 Oktober 2026)

- Django supported series: https://www.djangoproject.com/download/
- Django 5.2 deployment checklist: https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/
- Compose services/resource limits: https://docs.docker.com/reference/compose-file/services/
- Compose networking: https://docs.docker.com/compose/how-tos/networking/
- Published port/loopback caveat: https://docs.docker.com/engine/network/port-publishing/
- Tailscale SSH: https://tailscale.com/docs/features/tailscale-ssh

Ini adalah implementasi khusus, bukan paket yang diterbitkan atau disertifikasi
oleh Django, Docker, Tailscale, Cloudflare atau vendor mesin.
