# 10 - Dasar dokumentasi, referensi, dan validasi

[Kembali ke indeks](README.md)

## 1. Dasar yang dibaca

Dokumentasi disusun dari arsip source `multitek-pm-v0.1-source.zip`, script
perbaikan/Cloudflare/ekspor Git yang tersedia dalam percakapan, dan log instalasi
PM v0.1.1 dari pengguna. Kode bisnis dibaca langsung: models, services, views,
forms, importing, scheduling, management commands, admin, template, URL,
Compose, requirements, serta helper operasi.

Tidak ada koneksi langsung yang berhasil ke repository privat atau VPS saat
penyusunan. Karena itu, script publikasi mencocokkan fingerprint berkas baseline
di checkout VPS sebelum menambahkan buku ini. Berkas settings diterima dalam
versi pilot asli atau versi dengan patch Cloudflare HTTPS yang telah tersedia.
File bisnis yang berbeda tidak ditimpa atau didokumentasikan seolah-olah sama.

[baseline.json](baseline.json) memuat SHA-256 source pembanding. Saat push,
[publikasi.json](publikasi.json) ditulis script dengan commit source dan waktu
verifikasi aktual. Di paket unduhan, berkas itu berstatus belum_dijalankan; script akan menggantinya
dengan catatan pemeriksaan checkout yang sebenarnya.

## 2. Batas bukti

Log instalasi mencatat 33 tes SQLite lulus, migrasi PostgreSQL dan health aplikasi
berhasil, serta guard layanan lama lolos. Log tersebut bukan hasil tes baru dari
penyusun dokumentasi, bukan audit seluruh data, dan bukan bukti backup/restore.

Validasi paket dokumentasi memeriksa konsistensi tautan/path/simbol source,
sintaks helper, proteksi file, dan alur Git dengan repository lokal. Pengujian
Git lokal tidak membuktikan hak tulis GitHub, policy branch, atau koneksi SSH VPS.
Tidak ada klaim dokumentasi sudah berada di GitHub sebelum verifikasi push.

## 3. Referensi eksternal (untuk praktik development/operasi)

Referensi berikut mendukung perintah umum; perilaku spesifik PM tetap mengacu
pada source, bukan diisi berdasarkan fitur produk lain.

- [Django: writing and running tests](https://docs.djangoproject.com/en/5.2/topics/testing/overview/)
- [Django: migrations](https://docs.djangoproject.com/en/5.2/topics/migrations/)
- [Django: deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/)
- [GitHub flow](https://docs.github.com/en/get-started/using-github/github-flow)
- [Git push](https://git-scm.com/docs/git-push)
- [Git ignore](https://git-scm.com/docs/gitignore)
- [Docker Compose up](https://docs.docker.com/reference/cli/docker/compose/up/)
- [Cloudflare: self-hosted applications](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/self-hosted-public-app/)

Referensi ditinjau pada 15 Oktober 2026. Menu pihak ketiga dan versi dependensi
bisa berubah; cek dokumentasi versi yang benar sebelum perubahan operasional.

## 4. Merawat akurasi berikutnya

Perbarui manual ketika label/aturan/izin berubah. Perbarui peta kode bila modul
berpindah. Bukti validasi setiap rilis harus menyebut commit dan lingkungan.
Nomor versi di footer, health endpoint, dan paket belum tersentralisasi; jangan
menganggap label tunggal selalu cukup untuk mengidentifikasi source runtime.
