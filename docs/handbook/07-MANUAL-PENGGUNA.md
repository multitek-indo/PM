# Manual pengguna Multitek Smart Maintenance

**Edisi 1.0 - 15 Oktober 2026**
**Untuk admin, supervisor maintenance, dan teknisi**

[Kembali ke indeks](README.md)

## 1. Fungsi dan batas aplikasi

Multitek Smart Maintenance mencatat mesin, jadwal preventive maintenance (PM),
work order (WO), hasil checklist, dan verifikasi supervisor. PM adalah pekerjaan
pemeliharaan terjadwal; WO adalah satu tugas pada satu tanggal jatuh tempo.

Aplikasi tidak mengukur mesin secara otomatis dan tidak menggantikan manual
mesin, SOP keselamatan, atau penilaian teknisi. Status **Disetujui** berarti
hasil pekerjaan telah diverifikasi, bukan sertifikat bahwa mesin aman dijalankan.
Temuan tidak normal masih dapat membutuhkan tindak lanjut di luar aplikasi.

Panduan mengikuti menu yang tersedia pada baseline v0.1. Tautan domain akhir,
status backup, dan konfigurasi Cloudflare di akun Anda tidak dibuktikan hanya
oleh panduan ini. Nama, tanggal, dan mesin contoh dalam buku ini adalah data uji.

## 2. Peran dan kewenangan

| Kegiatan | Teknisi | Supervisor PM | Admin superuser |
|---|---|---|---|
| Login, ganti password | Ya | Ya | Ya |
| Melihat master mesin/jadwal mesin | Ya, seluruh master | Ya | Ya |
| Melihat daftar WO | Yang ditugaskan kepada dirinya | Seluruh tim | Seluruh tim |
| Mengisi checklist WO | Hanya WO miliknya berstatus open | Hanya jika ditugaskan kepadanya | Hanya jika ditugaskan kepadanya |
| Mengalihkan WO open | Tidak | Ya | Ya |
| Menyetujui/mengembalikan hasil | Tidak | Ya, bukan hasil sendiri | Ya, bukan hasil sendiri |
| Impor mesin/ekspor WO | Tidak | Ya | Ya |
| Master mesin/jadwal via Administrasi | Tidak secara default | Perlu staff dan permission sesuai | Ya |
| Mengelola akun pengguna | Tidak | Tidak secara default | Ya |

Grup **Supervisor PM** menentukan akses supervisor. Status **Staff** menentukan
akses ke admin site, bukan otomatis memberikan hak supervisor. Grup **Teknisi PM**
dipakai sebagai label peran; user biasa yang login tetap diperlakukan sebagai
teknisi terbatas untuk WO. Master mesin belum dibatasi per pabrik/tenant.

## 3. Login, password, dan keluar

Buka alamat aplikasi yang sudah diberikan admin. Jika memakai Cloudflare Access,
selesaikan verifikasi identitas lebih dahulu, lalu login aplikasi dengan akun PM.
Login Cloudflare dan login PM belum digabung menjadi satu login otomatis.

Pilih **Ganti password**, isi password lama dan password baru sesuai permintaan,
kemudian simpan. Baseline menerapkan panjang minimal 12 karakter serta pemeriksaan
password umum/numerik/kemiripan identitas. Jangan berbagi akun antarorang karena
nama akun tercatat dalam hasil pekerjaan.

Pilih **Keluar** setelah selesai, terutama pada HP bersama. Ketika password lupa,
hubungi admin; alur reset password mandiri lewat email belum disediakan. Jangan
meminta admin mengirim file kredensial server.

## 4. Mengenali halaman Ringkasan

| Bagian | Cara membacanya |
|---|---|
| Mesin aktif | Jumlah mesin active pada seluruh master; bukan hanya mesin teknisi saat ini |
| Pekerjaan terbuka | Belum dikirim; dapat termasuk tugas yang dibuat sebelum due |
| Melewati jatuh tempo | Sudah melewati tanggal due dan belum disetujui; termasuk menunggu verifikasi |
| Menunggu verifikasi | Sudah dikirim teknisi, belum diputuskan supervisor |
| PM tepat waktu | Sudah disetujui dan terakhir dikirim pada/sebelum due, dari WO due bulan ini sampai hari ini |
| Penjadwalan otomatis | Heartbeat terakhir generator; indikator terlambat jika lebih dari 15 menit |

Angka WO teknisi hanya mencakup tugas miliknya; supervisor melihat seluruh tim.
Jika belum ada due dalam periode, PM tepat waktu menampilkan tanda kosong, bukan
100%. Contoh: 7 dari 10 tugas due sudah disetujui dan dikirim tepat waktu berarti
70,0%. Ini bukan persentase mesin sehat.

**Prioritas pekerjaan** menampilkan maksimal 10 WO belum disetujui menurut
urutan due/id. Gunakan menu Work order untuk daftar lengkap yang dapat diakses.
Jangan membuat ulang jadwal hanya karena heartbeat terlambat; laporkan ke admin.

## 5. Menyiapkan pengguna - admin

Masuk menggunakan akun superuser, buka **Administrasi**, lalu bagian pengguna
Django. Label bawaan bisa mengikuti terjemahan Django. Buat username unik untuk
satu orang, password kuat, dan aktifkan akun.

Untuk teknisi: masukkan ke **Teknisi PM**; tidak perlu Staff atau Superuser.
Untuk supervisor: masukkan ke **Supervisor PM**. Aktifkan Staff hanya bila ia
perlu mengelola master melalui Administrasi. Jangan menjadikan seluruh teknisi
superuser agar menu terlihat.

Pilihan teknisi menggunakan daftar user aktif, sehingga secara teknis admin atau
supervisor aktif juga dapat dipilih. Pilih orang yang benar-benar bertanggung
jawab. Akun pengisi dan pemberi persetujuan harus mewakili orang berbeda dalam
penggunaan nyata; dua akun milik satu orang bukan pemisahan tugas yang efektif.

Catatan pilot: autocomplete pemilihan user pada form jadwal admin juga mengikuti
permission model User. Bootstrap belum memberi permission auth ke Supervisor PM.
Bila pencarian teknisi di sana ditolak, minta admin menyiapkan jadwal/penugasan
awal; jangan membagikan superuser sebagai jalan pintas. Penugasan pada halaman
WO memakai form berbeda.

## 6. Menambahkan dan mengelola mesin

Dari **Master mesin**, pilih **Tambah mesin** dengan akun staff berizin. Atau
buka **Administrasi -> Mesin**. Isi **Kode mesin** dan **Nama mesin**; keduanya
wajib. Kode unik menjadi identitas yang dipakai untuk pencarian dan pekerjaan.

| Kolom | Isi yang dianjurkan |
|---|---|
| Kode mesin | Kode aset internal unik, misalnya `TEST-SW-001` untuk uji |
| Nama mesin | Nama yang mudah dikenali teknisi |
| Jenis mesin | Kategori internal, tidak dibatasi daftar kategori baku |
| Merek / Model / Serial number | Sesuai label/dokumen mesin; jangan menebak |
| Pabrik / lokasi dan Line produksi | Gunakan ejaan konsisten |
| Aktif dalam pemeliharaan | Aktif jika boleh dibuatkan pekerjaan baru |
| Catatan | Informasi mesin yang relevan, bukan password atau data rahasia |

Simpan, buka kembali detail mesin, dan periksa kode/lokasi. Pencarian master
mencakup kode, nama, pabrik, line, dan serial. Daftar dipaginasi 50 mesin per
halaman. Tidak ada filter merek khusus pada baseline.

Untuk mesin keluar dari pemeliharaan, ubah **Aktif dalam pemeliharaan** menjadi
nonaktif. Pekerjaan baru dari mesin itu berhenti dibuat; WO yang sudah terbentuk
dan riwayatnya tidak otomatis dihapus. Hindari penghapusan master yang dipakai
untuk riwayat. Perubahan lokasi master juga akan tampil pada laporan WO lama
karena lokasi belum disnapshot per pekerjaan.

## 7. Impor banyak mesin melalui CSV

Buka **Master mesin -> Impor CSV -> Ambil template CSV kosong**. Header berikut
harus tersedia dengan ejaan yang sama dan pemisah koma:

```csv
code,name,category,manufacturer,model,serial,site,line
TEST-SW-001,Mesin uji,Lockstitch,Contoh Merek,Model Uji,SERIAL-UJI,PABRIK-UJI,LINE-UJI
```

Baris kedua hanya contoh, bukan master siap produksi. Isi code dan name; nilai
kolom lainnya boleh kosong tetapi kolom/header tetap ada. Gunakan CSV UTF-8;
BOM UTF-8 diterima. Jika memakai Excel, pastikan pemisah sebenarnya koma, bukan
titik koma, dan kode/serial yang mengandung nol awal tidak berubah.

Pilih file, kemudian **Validasi dan impor**. Batas satu file adalah 2 MiB dan
5.000 mesin. Impor hanya menambah data baru, bukan memperbarui kode lama.

Jika ada kode duplikat dalam file, kode sudah tersimpan, nilai tidak valid,
kolom tidak lengkap, atau file terlalu besar, seluruh impor dibatalkan. Benahi
file dan coba kembali; jangan mengganti kode mesin lama hanya agar lolos.

**Impor mesin tidak membuat jadwal PM.** Sesudah impor, buat Plan sesuai kebutuhan
mesin. Baseline belum mempunyai impor jadwal massal.

## 8. Membuat jadwal PM - admin/supervisor berizin

Dari detail mesin, pilih **Tambah jadwal**, atau gunakan **Administrasi ->
Jadwal PM**. Pilih mesin yang tepat, nama pekerjaan, interval hari, tanggal
**Jatuh tempo berikut yang belum dibuat**, teknisi aktif, dan checklist.

Interval diterima antara 1 dan 3.650 hari. Pilih interval berdasarkan manual
mesin/SOP dan kondisi operasi, bukan angka contoh di panduan. Tanggal dibatasi
maksimal tahun 2090 pada validasi Plan. Untuk uji, gunakan tanggal dekat hari ini
agar tidak menghasilkan backlog besar.

Checklist berisi satu pemeriksaan per baris: 1-30 baris, maksimal 240 karakter
per baris. Hilangkan baris kosong. Gunakan instruksi yang dapat diamati dan sesuai
kewenangan teknisi; jangan menuliskan tindakan berbahaya tanpa prosedur resmi.

Simpan dengan **Jadwal aktif** tercentang. Generator memeriksa setiap sekitar
5 menit dan membuat tugas sampai 7 hari sebelum due. Waktu itu bukan janji
notifikasi real-time; jika generator gagal, heartbeat menunjukkan keterlambatan.

Tanggal berikut bergerak setelah WO dibuat, bukan setelah selesai. Contoh uji:
Plan due 20 Oktober dengan interval 30 hari dapat menunjukkan next_due 19 November
sementara WO 20 Oktober masih terbuka. Periksa WO, jangan menyimpulkan pekerjaan
Oktober hilang atau selesai.

## 9. Mengubah jadwal atau teknisi

Ubah Plan bila template/interval/teknisi untuk **pekerjaan mendatang** berubah.
WO yang sudah terbentuk mempertahankan judul dan checklist snapshot. Mengubah
teknisi di Plan juga tidak memindahkan WO yang sudah ada.

Untuk mengalihkan WO yang sudah terbentuk, supervisor membuka **Work order**,
pilih WO berstatus **Belum dikerjakan**, buka **Penugasan teknisi**, pilih user
aktif, lalu **Simpan penugasan**. WO yang review/done tidak dapat dialihkan lewat
form ini. Jika tugas belum ditugaskan, hanya supervisor dapat melihatnya dalam
cakupan seluruh tim dan melakukan penugasan.

Nonaktifkan Plan untuk menghentikan pembuatan berikutnya tanpa membuang riwayat.
Tidak ada tombol pembatalan WO pada baseline. Jadwal salah yang sudah membuat WO
perlu prosedur koreksi terarah, bukan edit langsung database.

## 10. Mengerjakan work order - teknisi

Buka **Work order**, cari mesin/judul/pabrik atau pilih status. Pilih WO yang
benar. Cocokkan mesin fisik, due, nama pekerjaan, dan penugasan sebelum bekerja.
Ikuti SOP isolasi energi/manual yang relevan; formulir bukan izin melakukan
pekerjaan yang belum aman.

Pada **Pelaksanaan pemeriksaan**, jawab setiap poin dengan **Normal / sesuai
pemeriksaan** atau **Tidak normal / perlu tindak lanjut**. Tidak ada pilihan N/A
atau draft tersimpan otomatis. Jika ada item yang tidak bisa diperiksa, jangan
mengarang hasil Normal; catat situasinya dan koordinasikan prosedur dengan
supervisor sebelum menyelesaikan laporan.

Isi **Temuan / tindakan / catatan** maksimal 4.000 karakter. Jika ada jawaban
tidak normal, catatan wajib. Contoh catatan yang berguna: 'Pelindung tidak terpasang;
mesin belum dioperasikan; tindak lanjut menunggu supervisor sesuai SOP'. Catat
hanya kejadian sebenarnya; contoh ini bukan diagnosis teknis mesin Anda.

Tekan **Kirim untuk diverifikasi**. Harus muncul pesan bahwa hasil dikirim dan
status berubah menjadi **Menunggu verifikasi**. Saat koneksi gagal, buka ulang WO
untuk memastikan status sebelum mengirim lagi. Jangan menganggap klik berarti
tersimpan. Setelah dikirim, hasil tidak dapat diedit langsung oleh teknisi.

Tombol isi hanya muncul untuk user yang ditugaskan ketika status open. User lain,
termasuk supervisor yang bukan assigned_to, tidak dapat mengisi atas nama teknisi.

## 11. Memverifikasi - supervisor

Pilih filter **Menunggu verifikasi**, buka WO, baca checklist dan **Hasil terakhir
yang dikirim**, catatan, identitas pengirim, dan waktu. Gunakan bukti lapangan
sesuai SOP, bukan sekadar mengejar persentase dashboard.

Pada **Verifikasi supervisor**, pilih **Setujui pekerjaan** atau **Kembalikan ke
teknisi**. Untuk pengembalian, alasan wajib dan maksimal catatan 2.000 karakter.
Klik **Simpan keputusan**. Approve menghasilkan **Disetujui**; reject mengembalikan
ke **Belum dikerjakan**. Riwayat pengiriman dan keputusan tetap tercatat.

Form verifikasi tidak muncul untuk pengirim sendiri. Supervisor yang mengerjakan
WO harus meminta supervisor berbeda meninjaunya. WO done belum mempunyai alur
reopen/cancel pada baseline.

Jawaban tidak normal tidak otomatis melarang persetujuan. Supervisor bertanggung
jawab mencatat tindak lanjut di prosedur yang berlaku; aplikasi belum mempunyai
work order corrective terstruktur atau status izin operasi mesin.

## 12. Pekerjaan yang dikembalikan

Teknisi membuka kembali WO open, membaca alasan pengembalian pada **Riwayat
aktivitas**, dan melihat hasil terakhir pada panel terpisah. Form tidak otomatis
mengisi ulang jawaban lama. Kerjakan tindak lanjut yang disepakati, isi seluruh
jawaban dengan kondisi terbaru, dan kirim kembali.

Pengiriman ulang memperbarui waktu/hasil terakhir, sementara event lama tetap ada.
PM tepat waktu memakai pengiriman terakhir yang akhirnya disetujui; pengembalian
setelah due dapat memengaruhi indikator. Jangan memundurkan waktu server/data
untuk memperbaiki angka laporan.

## 13. Riwayat, QR, dan ekspor

Detail mesin menampilkan maksimal 30 WO sesuai akses dalam urutan due/id bawaan;
bukan jaminan seluruh riwayat atau 30 yang terbaru. Gunakan daftar WO dan ekspor
sesuai kebutuhan. Detail WO menampilkan maksimal 30 event terbaru; supervisor
berizin dapat membuka detail audit melalui Administrasi.

**Buka QR mesin** tersedia ketika origin publik diisi. Endpoint tetap menolak
origin yang bukan HTTPS valid tanpa path/query. Buka SVG, cetak label yang jelas,
dan uji satu QR dengan HP sebelum mencetak banyak. Hasil scan menuju detail mesin
dan tetap memerlukan login/Access. Pergantian domain dapat membuat label lama
tidak berfungsi; tidak ada pengalihan label otomatis yang dijanjikan baseline.

**Ekspor CSV** tersedia bagi supervisor dari halaman Work order. File memuat
maksimal 20.000 WO berdasarkan due/id paling baru dari **semua status**, bukan
filter yang sedang tampil. Filter/pilah file secara terpisah setelah unduhan
atau bangun fitur ekspor-filter dengan tes sebelum mengklaim laporan terfilter.

Kolom ekspor: id, mesin, pabrik, line, pekerjaan, jatuh_tempo, status, teknisi,
dikirim, disetujui, catatan. Export belum memuat seluruh JSON jawaban atau nama
approver. Periksa timezone pada data waktu ekspor; CSV memakai representasi nilai
datetime, tidak diformat khusus seperti tampilan WIB di HTML. Simpan ekspor di
lokasi yang diizinkan, jangan di repository source.

## 14. Masalah umum dan tindakan pengguna

| Gejala | Tindakan yang tepat |
|---|---|
| Daftar WO kosong | Periksa akun penugasan, filter, tanggal/horizon, mesin/Plan aktif; minta supervisor meninjau |
| Tidak ada tombol isi | WO bukan open atau bukan ditugaskan ke akun Anda |
| Hasil fail tidak bisa dikirim | Isi catatan tindak lanjut dan seluruh pilihan checklist |
| Tidak bisa menyetujui | Belum review, bukan supervisor, atau akun Anda pengirim |
| Impor ditolak | Baca pesan; cek UTF-8, koma, header, duplikat, jumlah, dan ukuran file |
| QR belum aktif | Admin perlu memverifikasi origin HTTPS dan konfigurasi publik |
| Heartbeat terlambat | Laporkan ke admin; jangan membuat ulang Plan/WO secara massal |
| Login publik ditolak | Periksa akses email/identitas melalui admin; jangan menonaktifkan Access sendiri |

## 15. Rutinitas harian dan batas versi

Teknisi memeriksa tugas, melaksanakan sesuai SOP, mencatat temuan, lalu memverifikasi
bahwa pengiriman tersimpan. Supervisor meninjau keterlambatan, WO tanpa teknisi,
hasil menunggu verifikasi, dan tindak lanjut fail. Admin memantau kesehatan
aplikasi/backup dan pengelolaan akun.

Belum tersedia: unggah foto/video, sensor/jam operasi otomatis, notifikasi
Telegram/WhatsApp/email, stok spare part, offline, pembatalan/reopen formal,
approval berjenjang, isolasi tenant, atau audit kebal perubahan admin server.
Gunakan hanya fitur yang sudah diuji untuk kebutuhan pabrik Anda.

Rujukan perilaku: [models](../../app/maintenance/models.py),
[services](../../app/maintenance/services.py), [views](../../app/maintenance/views.py),
[forms](../../app/maintenance/forms.py), [impor](../../app/maintenance/importing.py),
dan [template](../../app/templates/base.html). Untuk masalah teknis lanjutan,
lihat [troubleshooting](08-TROUBLESHOOTING.md).

## Tambahan versi 0.2

Menu impor kini menerima .xlsx langsung. Lihat [panduan rilis 0.2](../releases/0.2.md) untuk langkah dan batas file.
