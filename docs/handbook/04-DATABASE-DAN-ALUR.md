# 04 - Database, status, jadwal, dan KPI

[Kembali ke indeks](README.md)

Rujukan utama: [models.py](../../app/maintenance/models.py),
[services.py](../../app/maintenance/services.py),
[scheduling.py](../../app/maintenance/scheduling.py),
[views.py](../../app/maintenance/views.py).

## 1. Model dan relasi

| Model | Data inti | Relasi/aturan penting |
|---|---|---|
| Machine | uid, code, name, category, manufacturer, model, serial, site, line, active, notes | code unik; uid UUID unik; code/name wajib setelah strip |
| Plan | machine, title, interval_days, next_due, checklist, assigned_to, active | Satu mesin dapat memiliki beberapa Plan; interval 1-3650 hari |
| WorkOrder | plan, due_date, title, checklist_snapshot, assigned_to, status, answers, notes, submitted/approved fields | Unik pada plan + due_date; status open/review/done |
| AuditEvent | order (opsional), actor (opsional), action, detail JSON, created_at | on_delete PROTECT; bukan ledger anti-manipulasi |
| SchedulerState | name, last_ok, generated | name='pm'; jumlah dibuat pada putaran terakhir, bukan total historis |
| User / Group / Permission | Model bawaan Django | Group Supervisor PM untuk akses supervisor; staff untuk admin site |

```text
Machine 1 --- banyak Plan 1 --- banyak WorkOrder 1 --- banyak AuditEvent
User -> penugasan Plan/WO; pengirim, approver, dan actor audit
```

Master memakai PROTECT pada relasi yang dirujuk untuk mengurangi penghapusan
riwayat. Namun Machine/Plan yang belum dirujuk dapat tetap dihapus melalui admin
oleh pemilik permission. Dalam operasional, utamakan menonaktifkan, bukan hapus.

## 2. Status dan transisi

```text
open / Belum dikerjakan
  -> submit oleh user yang ditugaskan
review / Menunggu verifikasi
  -> approve oleh supervisor berbeda -> done / Disetujui
  -> reject + alasan oleh supervisor berbeda -> open
```

Tidak ada status resmi in_progress, cancelled, breakdown, atau rejected permanen.
'Terlambat' adalah kondisi turunan: status bukan done dan due_date lebih awal dari
hari ini di Asia/Jakarta. Status review juga dapat terlambat. WO due hari ini
belum masuk filter terlambat.

Pengirim harus sama dengan assigned_to. Supervisor pun tidak boleh mengisi WO
milik orang lain. Supervisor dapat mengalihkan WO open, tetapi tidak review/done.
Persetujuan menutup proses verifikasi; hasil fail tetap dapat ada. Sistem tidak
memaksa semua temuan fail menjadi normal sebelum approve, sehingga SOP corrective
maintenance di luar aplikasi masih diperlukan.

## 3. Kalender tetap dan pointer next_due

Generator membuat tanggal jatuh tempo sampai `hari_ini + 7 hari`. Jadwal
berikut dihitung dari tanggal due sebelumnya + interval, bukan tanggal selesai.

Contoh perhitungan (data fiktif): next_due 20 Oktober 2026, interval 30 hari,
hari proses 15 Oktober 2026. Horizon sampai 22 Oktober; WO untuk 20 Oktober dibuat,
lalu next_due menjadi 19 November 2026 meskipun WO Oktober belum dikerjakan.

Karena itu, kolom 'Berikut yang belum dibuat' adalah pointer generator, bukan
jaminan semua pekerjaan sebelum tanggal itu sudah diselesaikan. Lihat Work order
untuk pekerjaan terbuka/terlambat.

Satu Plan diproses maksimal 12 tanggal per putaran. Jika backlog lebih panjang,
next_due masih menunjuk backlog yang belum dibuat dan akan diproses putaran
berikutnya. Generator tidak menghapus backlog. Menyetel tanggal awal sangat lampau
untuk ribuan mesin dapat membuat banyak WO; jangan gunakan untuk mengimpor sejarah
lama secara sembarang.

Transaksi dan select_for_update mengurangi perlombaan antarproses pada PostgreSQL;
constraint unik merupakan perlindungan tambahan. Pengujian SQLite tidak cukup
untuk membuktikan konkurensi ini.

## 4. Snapshot dan perubahan master

Judul, checklist, dan penugasan awal disalin saat WO dibuat. Mengubah template
Plan tidak mengedit WO yang sudah terbentuk. Mengubah assigned_to pada Plan hanya
mempengaruhi WO mendatang; gunakan assign_order untuk WO open yang sudah ada.

Tanggal due/title/checklist WO tidak memiliki editor pengguna umum. Untuk
koreksi jadwal yang terlanjur salah, jangan mengganti nilai langsung di SQL.
Tentukan prosedur koreksi dengan histori/alasan sebelum membangun fiturnya.

Nama, site, line, merek, dan serial mesin tidak disnapshot di WO. Riwayat dibaca
melalui Machine saat ini. AuditEvent juga bukan snapshot lengkap sebelum/sesudah
untuk semua edit master; edit admin standar memiliki log admin tersendiri.

## 5. KPI yang benar-benar dihitung

| Indikator | Definisi source |
|---|---|
| Mesin aktif | Semua Machine dengan active=True, bukan hanya milik teknisi |
| Jadwal aktif | Semua Plan dengan active=True; tidak menyaring mesin nonaktif pada hitungan ini |
| Pekerjaan terbuka | WO visible berstatus open, termasuk WO masa depan yang telah dibuat |
| Melewati jatuh tempo | WO visible bukan done dan due_date < hari ini |
| Menunggu verifikasi | WO visible berstatus review |
| PM tepat waktu | WO visible due awal bulan s.d. hari ini, sudah done, submitted_at (tanggal) <= due_date; dibagi seluruh WO visible due periode itu |
| Persetujuan bulan ini | WO visible done dengan approved_at tanggal >= awal bulan |
| Heartbeat sehat | last_ok lebih baru dari sekarang dikurangi 15 menit |

Jika penyebut PM tepat waktu nol, dashboard menampilkan tanda kosong, bukan 100%.
Pembulatan satu digit desimal. Pengiriman sebelum due tetapi disetujui belakangan
baru masuk pembilang setelah status done; KPI dapat berubah setelah verifikasi.
Pengiriman ulang setelah reject menggunakan submitted_at terbaru.

Contoh: 10 WO jatuh tempo bulan berjalan sampai hari ini, 7 sudah disetujui dan
terakhir dikirim tepat waktu, maka indikator 70,0%. Ini contoh aritmetika, bukan
data produksi. Indikator bukan MTTR, MTBF, OEE, persentase mesin sehat, atau skor
kinerja teknisi tanpa konteks.

## 6. Audit yang ada

Action utama: `generated`, `assigned`, `submitted`, `approve`, `reject`, dan
`machine_import`. Detail submitted menyimpan jawaban dan catatan saat itu.
Pengembalian tidak menghapus event submitted terdahulu. Form berikutnya tidak
menyediakan draft otomatis; hasil terakhir ditampilkan pada panel terpisah.

Halaman detail WO menampilkan maksimal 30 event terbaru. Tidak semua isi detail
JSON ditampilkan di panel ringkas; pemeriksa berizin dapat membuka Riwayat
aktivitas melalui admin untuk detail lebih lengkap. Administrator database atau
server tetap dapat mengubah data di luar aplikasi.
