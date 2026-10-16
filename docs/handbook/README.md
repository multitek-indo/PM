# Buku panduan Multitek Smart Maintenance

**Repository: `multitek-indo/PM` | Edisi dokumentasi 1.0 | 15 Oktober 2026**

Panduan ini menjelaskan kode yang benar-benar tersedia dalam baseline aplikasi PM,
bukan seluruh fitur CMMS yang mungkin ditambahkan nanti. Label antarmuka masih
`PILOT v0.1`; patch installer/operasi dapat bernomor berbeda. Dokumentasi bukan
sertifikasi keselamatan mesin, audit keamanan, atau bukti pengujian beban produksi.

## Mulai dari kebutuhan Anda

| Kebutuhan | Dokumen yang dibaca |
|---|---|
| Belajar memakai aplikasi sebagai admin, supervisor, atau teknisi | [Manual pengguna](07-MANUAL-PENGGUNA.md) |
| Mengetahui file mana yang perlu diubah | [Peta kode dan fungsi](02-PETA-KODE.md) |
| Mulai coding tanpa menyentuh aplikasi produksi | [Panduan development](03-DEVELOPMENT.md) |
| Memahami data, penjadwalan, dan arti status | [Database dan alur bisnis](04-DATABASE-DAN-ALUR.md) |
| Menjalankan tes dan menilai hasilnya | [Panduan pengujian](05-PENGUJIAN.md) |
| Menyiapkan perubahan untuk produksi | [Deployment dan operasi](06-DEPLOYMENT-DAN-OPERASI.md) |
| Mencari penyebab error | [Troubleshooting](08-TROUBLESHOOTING.md) |
| Menentukan pekerjaan lanjutan | [Batasan dan roadmap](09-BATASAN-DAN-ROADMAP.md) |
| Memahami infrastruktur serta referensi | [Arsitektur](01-ARSITEKTUR.md), [sumber dan validasi](10-SUMBER-DAN-VALIDASI.md) |

## Empat hal yang berbeda

**Edit** mengubah file di salinan kerja. **Commit** mencatat revisi lokal.
**Push** mengirim revisi ke GitHub. **Deployment** menerapkan revisi ke aplikasi
produksi. Push atau merge pada repository ini tidak dengan sendirinya melakukan
deployment; paket dokumentasi tidak memasang auto-deploy.

```text
/opt/multitek-pm                         -> aplikasi produksi
/home/multitek/projects/multitek-pm      -> salinan kerja Git
GitHub: multitek-indo/PM                 -> riwayat kode dan dokumentasi
```

Jangan menjalankan `pmctl` dari salinan Git dengan anggapan itu lingkungan uji:
script tersebut selalu berpindah ke `/opt/multitek-pm`. Jangan menjalankan
`docker compose up` pada salinan kerja menggunakan Compose produksi.

## Panduan singkat yang disarankan

Untuk pengguna baru: login -> ganti password -> master mesin -> jadwal -> work
order -> kirim hasil -> verifikasi oleh orang berbeda -> ekspor bila diperlukan.

Untuk developer baru: baca peta kode -> buat branch -> jalankan tes baseline ->
ubah satu kebutuhan -> tes -> commit -> push branch -> Pull Request -> merge ->
rencanakan deployment tersendiri.

## Cara memelihara dokumentasi ini

Setiap perubahan perilaku harus memperbarui dokumen yang relevan pada commit atau
Pull Request yang sama. Contoh: perubahan horizon scheduler perlu memperbarui
services, tes, manual, dan penjelasan dashboard. Jangan menganggap fingerprint
baseline sebagai hash versi berikutnya; [baseline.json](baseline.json) merekam
source yang mendasari edisi ini, bukan daftar hash yang harus diubah otomatis.

Buku ini memakai istilah menu dari template baseline: **Ringkasan**, **Master
mesin**, **Work order**, **Administrasi**, **Ganti password**, dan **Keluar**.

## Pembaruan setelah baseline

[Rilis 0.2: UI, jam WIB, dan Excel](../releases/0.2.md) memperbarui panduan impor CSV lama.
