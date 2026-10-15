# 05 - Pengujian dan kriteria lulus

[Kembali ke indeks](README.md)

## 1. Jalankan tes tanpa produksi

Gunakan blok perintah tes pada [development](03-DEVELOPMENT.md). Selalu sertakan
`--settings=config.test_settings`, PM_HTTPS=0, dan secret khusus tes. Jangan
menjalankan test command dari container produksi dengan konfigurasi default.
Django menyediakan database tes terpisah, tetapi konfigurasi yang dipilih tetap
menentukan server/engine yang diakses. Baca [dokumentasi tes Django](https://docs.djangoproject.com/en/5.2/topics/testing/overview/).

File `config/test_settings.py` mengganti engine menjadi SQLite in-memory,
menggunakan hasher MD5 untuk mempercepat tes, dan menerima host testserver.
**Hasher tes ini tidak boleh digunakan untuk akun produksi.**

## 2. Kelompok tes baseline

| Kelompok | Apa yang diperiksa oleh source tests |
|---|---|
| Jadwal | Kalender tetap, idempotensi generator, backlog tidak hilang, mesin/jadwal nonaktif, interval invalid |
| Workflow | Submit, reject/approve, larangan approve sendiri, submit ganda, penugasan dan audit |
| Validasi | Checklist, fail memerlukan catatan, pengembalian memerlukan alasan, semua item terjawab |
| Izin | Login diperlukan, WO teknisi lain tidak terbuka, teknisi bukan importer/approver |
| CSV | Impor valid, duplikat/invalid membatalkan semua, proteksi awalan formula pada ekspor |
| UI dasar | Login, beberapa template, health, QR aktif/nonaktif, ekspor |

Daftar test method yang benar-benar ada pada saat penyusunan ada di
[simbol-source.md](simbol-source.md). Test suite baseline berisi 33 metode, bukan
33 modul. Log instalasi pengguna mencatat 33 test selesai; dokumentasi ini tidak
mengubah klaim itu menjadi bukti uji beban atau browser semua perangkat.

## 3. Tes yang wajib ditambah per jenis perubahan

| Perubahan | Tes minimal tambahan |
|---|---|
| Kolom data baru | Nilai kosong/valid/invalid, migrasi data lama, form, impor/ekspor |
| Hak akses | User tanpa grup, teknisi A/B, supervisor, staff tanpa grup, superuser, user nonaktif |
| Penjadwalan | Tanggal batas horizon, interval batas, backlog >12, pengulangan generator, konkurensi PostgreSQL |
| Form hasil | Semua jawaban, missing answer, fail tanpa catatan, dua request bersamaan |
| KPI | Nol penyebut, due hari ini, sebelum/sesudah due, persetujuan tertunda, timezone, reject-resubmit |
| Tampilan | Desktop/HP, pesan validasi panjang, empty state, pencarian, pagination |
| HTTPS/QR | Domain benar/salah, cookie Secure, CSRF benar/salah, QR setelah login, Access |

## 4. Uji penerimaan manual dengan data fiktif

Buat mesin `TEST-SW-001` dan dua akun nyata untuk sesi uji (teknisi dan supervisor).
Isi satu Plan aktif dengan tanggal dalam horizon. Pastikan generator membuat satu
WO dan tidak menduplikasinya ketika dipanggil ulang. Isi satu hasil fail + catatan,
kirim, kembalikan dengan alasan, kirim ulang, lalu setujui dengan akun berbeda.
Periksa status, actor, waktu, dan riwayat. Jangan mencampur uji dengan laporan
keuangan/operasional resmi.

Periksa bahwa akun teknisi tidak dapat membuka URL WO teknisi lain; supervisor
bisa menugaskan ulang open; master mesin masih terbaca oleh user login. Jangan
menganggap cakupan master tersebut sebagai isolasi antarperusahaan.

## 5. Bukti sebelum review

Catat commit yang diuji, versi Python dan dependensi, database yang dipakai,
perintah tes, ringkasan output, skenario manual, hasil aktual, dan keterbatasan.
Jangan menempel .env atau screenshot password ke Pull Request. Hasil tes sukses
pada laptop tidak membuktikan staging/produksi identik.

## 6. Hal yang belum dibuktikan baseline

Belum ada bukti pengujian beban ribuan pengguna serentak, failover, pemulihan
bencana, semua browser mobile, penetrasi keamanan, atau isolation tenant.
Scheduler menggunakan lock PostgreSQL; uji konkurensinya harus memakai database
staging PostgreSQL. Belum ada pipeline CI otomatis yang dibuat oleh paket dokumen.
