# 08 - Troubleshooting tanpa merusak layanan

[Kembali ke indeks](README.md)

## 1. Urutan pemeriksaan

Catat URL/aksi, waktu, akun/peran, pesan error tanpa rahasia, dan commit yang
berubah. Bedakan masalah browser/Access, aplikasi, database, dan Git.
Pengujian pertama harus lokal, aman, dan tidak mengubah data kecuali memang
sedang menjalankan skenario uji. Jangan menghapus database/volume untuk
mengatasi pesan yang belum dibaca.

## 2. Error aplikasi

| Gejala | Pemeriksaan | Yang jangan dilakukan |
|---|---|---|
| 400 dari Django | Domain pada browser/Host cocok PM_ALLOWED_HOSTS | Memakai wildcard `*` tanpa alasan |
| 403 CSRF | Domain HTTPS, PM_CSRF_ORIGINS, trusted proxy, cookie, sesi baru | Mematikan CsrfViewMiddleware |
| 502 dari Cloudflare | Tunnel host benar, HTTP ke 127.0.0.1:18080, health lokal | Mengubah origin ke HTTPS bila web hanya HTTP |
| Redirect berulang | PM_HTTPS, public origin, X-Forwarded-Proto, skema browser | Membuka port aplikasi langsung ke internet |
| Health 503 | Status database PM dan log PM | Mengubah database Odoo/Nextcloud |
| Tugas tidak muncul | Plan/mesin aktif, next_due <= today+7, assignment, heartbeat | Memundurkan jadwal jauh tanpa menghitung backlog |
| No module named ... | venv/package yang dipakai, versi requirements | `sudo pip install` pada OS produksi |
| Error PM_SECRET_KEY saat tes | Secret tes belum diekspor | Menyalin secret produksi ke kode tes |
| no such table saat preview | Gunakan dev_settings persisten lalu migrate dev | Menggunakan test_settings in-memory untuk server harian |

Semua detail sebab tetap perlu dicocokkan dengan output aktual; tabel bukan
kepastian diagnosis. `ops/local_check.py` masih menyasar pilot HTTP dan tidak
mengirim header proxy untuk skenario publik; redirect setelah patch HTTPS tidak
secara otomatis membuktikan aplikasi rusak.

## 3. Error Git

`Permission denied (publickey)`: gunakan akun Linux dan konfigurasi repository
yang sebelumnya berhasil. Pengaturan core.sshCommand lokal bisa berbeda dari
`ssh -T git@github.com` default. Jangan mencetak private key atau menggantinya.

`non-fast-forward`: remote berubah; fetch dan baca graph commit, jangan force
push rutin. Persetujuan force push saat baseline awal bukan alasan menimpa
perubahan dokumentasi/fitur berikutnya.

`STOP GUARD`: baca nama file yang disebutkan. `.env`, backup, database, media,
CSV/XLSX, dan PDF biner tidak diizinkan guard baseline. Manual PDF dibagikan
terpisah; Markdown manual yang disimpan di GitHub. Jangan memakai --no-verify.

`terminal tidak tersedia` pada initializer lama: masalah input script lama
sudah memiliki patch terpisah. Publikasi dokumentasi tidak meminta prompt
terminal atau mengeksekusi initializer itu kembali.

## 4. Pemeriksaan Git sekali blok

```bash
cd /home/multitek/projects/multitek-pm &&
printf '\n=== STATUS ===\n' && git status --short &&
printf '\n=== BRANCH ===\n' && git branch --show-current &&
printf '\n=== REMOTE ===\n' && git remote -v &&
printf '\n=== RECENT COMMITS ===\n' && git log --oneline -6 &&
printf '\n=== REMOTE MAIN ===\n' && git ls-remote --refs origin refs/heads/main
```

Jangan menambahkan dump `.git/config` atau isi semua environment ke laporan.
Bila SSH command memakai kredensial khusus, jangan membagikannya tanpa redaksi.

## 5. Jika publikasi dokumen terputus

Script dokumentasi tidak force push, tidak pull otomatis, dan tidak menimpa
perubahan pengguna yang belum disimpan. Jika remote maju, commit dokumentasi
lokal tetap ada; review dan integrasikan perubahan sebelum mencoba push lagi.
Gunakan petunjuk output script, bukan initializer/force-push baseline lama.

Sebelum membagikan error, singkirkan token, password, email pribadi yang tidak
relevan, dan data mesin pelanggan. Jangan menyatakan seluruh data hilang hanya
karena halaman tidak dapat dibuka; periksa lapisan yang gagal terlebih dahulu.
