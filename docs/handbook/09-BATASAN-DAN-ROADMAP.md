# 09 - Batasan dan rencana pengembangan

[Kembali ke indeks](README.md)

## 1. Batasan saat ini, bukan janji fitur

Source mendukung PM berbasis hari, bukan pembacaan jam mesin. Antarmuka merupakan
web HTML responsif, bukan aplikasi offline/PWA lengkap. Filter mesin belum
mencakup seluruh kolom; CSV ekspor tidak mengikuti filter layar dan dibatasi
20.000 WO. Riwayat tampilan dipotong untuk pilot. Riwayat kode Git tidak
menggantikan backup data.

Belum ada lampiran foto, notifikasi, stok/biaya spare part, corrective workflow,
reopen/cancel formal, tenant isolation, approval berjenjang, API umum,
high availability, maupun ledger audit tahan manipulasi administrator.

## 2. Urutan pengembangan yang disarankan (belum diterapkan)

| Tahap | Keluaran | Syarat sebelum lanjut |
|---|---|---|
| A - Keandalan | Backup dan restore diuji; staging PostgreSQL; pemantauan kapasitas | Bukti restore dan prosedur rollback |
| B - Kualitas operasional | Filter ekspor sesuai layar, koreksi/reopen/cancel beralasan, permission autocomplete | Tes akses, histori dan KPI |
| C - Bukti lapangan | Lampiran terbatas, kebijakan ukuran/retensi/akses | Rencana storage, proteksi file, backup |
| D - Pemberitahuan | Reminder dan eskalasi | Dedup notifikasi, batas frekuensi, secret management |
| E - Skala organisasi | Isolasi site/tenant dan laporan lebih lengkap | Audit semua queryset, endpoint, admin dan ekspor |
| F - Integrasi mesin | Counter jam/cycle/sensor untuk model yang mendukung | Survei perangkat, validasi data, keamanan jaringan |

Tidak semua tahap harus dilaksanakan sekaligus. Pilih satu masalah pengguna yang
terukur. Perubahan kosmetik dapat mendahului fitur berisiko, tetapi tidak boleh
mengaburkan indikator atau menghilangkan pesan keselamatan.

## 3. Contoh Issue siap dipakai

**Judul:** Ekspor WO mengikuti pencarian dan status layar.

**Kondisi sekarang:** tombol ekspor mengambil semua status dengan batas 20.000,
sehingga pengguna dapat keliru mengira file mengikuti filter.

**Target:** parameter pencarian/status diproses oleh filter bersama untuk daftar
dan ekspor; kontrol akses tetap berlaku; batas ekspor dijelaskan.

**Berkas:** views.py, orders.html, tests.py, manual pengguna, CHANGELOG.

**Kriteria lulus:** open/review/done/overdue dan pencarian sama antara layar dan
file; teknisi tetap ditolak; formula-safe_cell tetap diterapkan; data >batas
menghasilkan pemberitahuan yang jelas; tes lolos.

## 4. Hal yang perlu diputuskan sebelum coding

Definisi metrik, pihak yang boleh mengoreksi hasil, retensi bukti, jam operasi
resmi, aturan lintas pabrik, dan kebutuhan persetujuan harus disepakati pemilik
proses. Jangan mengisi celah proses dengan mengubah angka database secara diam-diam.
