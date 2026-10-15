# 02 - Peta kode: bagian yang diubah dan fungsinya

[Kembali ke indeks](README.md)

## 1. Pilih file berdasarkan kebutuhan

| Perubahan yang diinginkan | Titik utama | Yang juga wajib diperiksa |
|---|---|---|
| Warna, ukuran, tata letak | `app/static/pm.css` | Semua template, tampilan HP/desktop, cache CSS |
| Nama aplikasi, navigasi, footer | `app/templates/base.html` | Login dan label admin di `config/urls.py`; nama pada health endpoint |
| Kartu/angka dashboard | `maintenance/views.py:dashboard` dan `templates/dashboard.html` | Definisi KPI, hak akses, tes data tanggal batas |
| Tambah atribut mesin | `maintenance/models.py:Machine` | Migrasi, admin, impor/ekspor, pencarian, template, tests |
| Tampilan tambah/edit master | `maintenance/admin.py` | Permission Django admin dan validasi model |
| Pencarian mesin/WO | `maintenance/views.py:machines/orders` | Indeks DB, batas input, pagination, permission |
| Kolom impor CSV | `maintenance/importing.py:FIELDS/import_csv` | Header template, teks halaman impor, validasi atomik, tes |
| Validasi hasil checklist | `maintenance/forms.py:ChecklistForm` dan `services.py:submit_order` | Validasi server harus tetap ada meskipun form diubah |
| Horizon pembuatan WO | `maintenance/services.py:generate_orders` | Teks dashboard, manual, tes jadwal |
| Batas backlog/perhitungan interval | `maintenance/scheduling.py:due_dates` | Constraint interval pada model dan migrasi bila diubah |
| Frekuensi proses scheduler | `management/commands/pm_scheduler.py` | Ambang heartbeat di dashboard; bukan interval PM mesin |
| Persetujuan/pengembalian | `maintenance/services.py:review_order` | `order_detail`, ReviewForm, audit, tes pemisahan tugas |
| Pembagian tugas | `maintenance/services.py:assign_order` | Plan untuk tugas masa depan, WO untuk tugas yang sudah terbentuk |
| Akses supervisor/teknisi | `maintenance/services.py:supervisor/visible_orders` | Views, admin permission, bootstrap, tes lintas pengguna |
| QR mesin | `maintenance/views.py:machine_qr` | Domain HTTPS dari konfigurasi, login, label fisik |
| Kolom laporan CSV | `maintenance/views.py:export_orders` | `safe_cell`, batas 20.000, kebijakan filter, tes |
| URL/menu baru | `app/config/urls.py` | View, template navigasi, permission, tes route |
| Dependensi Python | `requirements.txt` | Lock versi, package volume, tes dan deployment terpisah |
| CPU, RAM, port, command container | `compose.yaml` | Baseline layanan, restart terarah, origin Cloudflare |
| Hostname, cookie, proxy HTTPS | `app/config/settings.py` dan `.env` privat | Origin/CSRF/redirect/QR; nilai rahasia tidak masuk Git |

Path tanpa awalan `app/` pada tabel masih relatif terhadap direktori `app/`.

## 2. Tanggung jawab modul

### Data: `models.py`

`Machine` menyimpan identitas mesin. `Plan` menyimpan template pekerjaan berulang.
`WorkOrder` adalah satu kejadian pekerjaan dengan tanggal jatuh tempo tertentu.
`AuditEvent` mencatat tindakan. `SchedulerState` menyimpan heartbeat generator.

Jangan menaruh semua aturan workflow hanya di model/form. Baseline memusatkan
transaksi submit/review/assign pada `services.py`. Model tetap menyediakan
constraint untuk interval valid dan pasangan unik plan/tanggal.

### Aturan bisnis: `services.py`

`supervisor(user)` memeriksa user aktif dan status superuser atau grup
`Supervisor PM`. `visible_orders(user)` mengembalikan seluruh WO untuk supervisor,
atau hanya WO yang ditugaskan ke user tersebut.

`generate_orders(today=None)` memilih jadwal aktif, mengunci tiap Plan dalam
transaksi, membuat snapshot judul/checklist/teknisi, memperbarui next_due,
mencatat audit, dan memperbarui heartbeat. `today` dapat diberikan untuk tes.

`submit_order(pk,user,results,notes)` memastikan penugasan cocok, status open,
semua hasil valid, catatan cukup, lalu menyimpan review + audit. `review_order`
memastikan supervisor berbeda dari pengirim dan menulis done atau open.
`assign_order` hanya mengalihkan WO open kepada user aktif; master Plan tidak
ikut berubah.

### HTTP: `views.py`

Views membaca request, mengecek akses, memanggil service, kemudian merender
HTML/CSV/SVG/JSON. Pemindahan filter ke JavaScript saja tidak cukup untuk kontrol
akses; pemeriksaan server wajib dipertahankan. `healthz` hanya menjalankan
`SELECT 1`, bukan pemeriksaan kelengkapan data, backup, atau kualitas PM.

### Form: `forms.py`

Form membuat pilihan dan batas panjang input agar pengguna memperoleh pesan
validasi. Rules penting tetap diperiksa ulang di service untuk mencegah bypass
ketika request dikirim tanpa browser.

### Scheduler: `scheduling.py` dan command

`due_dates()` adalah fungsi perhitungan tanggal murni, tanpa database.
`pm_scheduler` adalah proses yang terus berjalan dan mengelola jeda/koneksi serta
sinyal penghentian. `--once` menjalankan satu putaran dan boleh membuat data WO;
ini bukan perintah pemeriksaan read-only.

### Admin: `admin.py`

MachineAdmin dan PlanAdmin mengatur form/list/pencarian. WorkOrder, AuditEvent,
dan SchedulerState memakai ReadOnlyAdmin: tidak ditambah, diubah, atau dihapus
melalui halaman admin. Jangan mengubah ini hanya agar pekerjaan bisa 'cepat
selesai'; perubahan status harus melalui service agar audit dan validasi terjaga.

## 3. URL baseline

| URL | Fungsi |
|---|---|
| `/healthz` | Respons status koneksi database, tanpa halaman login |
| `/login/`, `/logout/`, `/password/` | Login, logout POST, ganti password |
| `/` | Ringkasan |
| `/admin/` | Admin Django untuk user staff berizin |
| `/machines/` | Daftar/pencarian mesin |
| `/machines/import/`, `/machines/template.csv` | Impor supervisor dan template header |
| `/machines/<uuid>/` | Detail mesin dan riwayat sesuai akses |
| `/machines/<uuid>/qr.svg` | SVG QR bila origin HTTPS valid |
| `/orders/`, `/orders/export.csv` | Daftar WO dan ekspor supervisor |
| `/orders/<id>/` | Detail, submit, assign, atau review |

Rujukan: [urls.py](../../app/config/urls.py),
[views.py](../../app/maintenance/views.py).

## 4. File yang bukan tempat edit fitur sehari-hari

`migrations/0001_initial.py` adalah riwayat skema awal; buat migrasi baru, jangan
mengubahnya setelah diterapkan. `db-init/10-pm-role.sh` menyiapkan role pada volume
baru; mengeditnya tidak otomatis mengubah database yang sudah ada. `pm_bootstrap`
hanya bootstrap awal dan menolak menimpa admin yang sudah dibuat.

`ops/guard.py` melindungi baseline operasi; `ops/local_check.py` adalah pemeriksa
pilot HTTP dan dapat tidak sesuai setelah redirect HTTPS aktif. Jangan melemahkan
guard atau menafsirkan local_check sebagai pemeriksaan Cloudflare lengkap.

`tools/git_safety.py` dan `.githooks/` membatasi file/rahasia sebelum commit/push.
`docs/source-snapshot.json` adalah catatan ekspor terdahulu, bukan file runtime.

## 5. Batas snapshot data

Judul, checklist, dan teknisi awal disalin ke WorkOrder saat dibuat. Identitas dan
lokasi mesin masih dibaca lewat relasi ke master Machine saat halaman/ekspor
terbuka. Mengubah site/line/nama master dapat mengubah konteks laporan historis;
belum ada snapshot seluruh atribut mesin. Tulis kebutuhan audit lokasi historis
sebagai fitur baru, jangan menjanjikannya pada pengguna sekarang.
