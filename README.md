# Multitek Smart Maintenance

Repository kode sumber untuk dashboard preventive maintenance Multitek Indonesia.
Sumber baseline disalin dari instalasi aktif saat script ekspor dijalankan, bukan
mengekstrak ulang installer lama. Lihat `docs/source-snapshot.json` untuk hash file.
Snapshot source bukan backup database, file upload, atau konfigurasi rahasia.

## Lokasi dan aturan keselamatan

- Produksi: `/opt/multitek-pm`.
- Salinan pengembangan awal: `/home/multitek/projects/multitek-pm`.
- Repository ini tidak berisi `.env`, `private/`, laporan, backup, atau database.
- Push/merge GitHub TIDAK melakukan deployment otomatis.
- Dilarang melakukan checkout branch atau git pull langsung pada kode produksi.
- PENTING: `pmctl` masih menunjuk ke `/opt/multitek-pm` dan `compose.yaml` memakai
  nama project `multitek-pm`. JANGAN menjalankan keduanya dari folder pengembangan
  dengan asumsi akan membuat lingkungan terpisah. Isolasi folder Git bukan
  isolasi Docker. Desain lingkungan staging dilakukan terpisah.
- `docs/README-installer-legacy.md` adalah catatan historis installer asli, bukan
  bukti semua instruksi/versinya masih mutakhir. Jangan memasang installer lama
  di atas instalasi yang sudah berjalan.

## Struktur

`app/`: Django, template, static source, migrasi skema dan tes.
`compose.yaml`, `db-init/`, `pmctl`: rancangan/operasi produksi; bukan dev runner.
`ops/`: kode operasional, termasuk guard yang saat ini tersimpan di produksi.
`tools/git_safety.py`, `.githooks/`: pemeriksaan lokal sebelum commit/push.
`docs/`: alur kerja, asal snapshot dan catatan arsitektur.
`.env.example`: nama variabel dan placeholder, bukan kredensial asli.

## Alur pengembangan

1. Buat Issue dengan masalah, target hasil, serta cara membuktikan keberhasilan.
2. Buat branch pendek per fitur/perbaikan dari `main`.
3. Edit hanya salinan kerja, jalankan tes, review `git diff`.
4. Commit kecil dengan pesan jelas; push branch, kemudian buat Pull Request.
5. Review sendiri atau bersama pihak berwenang; merge setelah tes lolos.
6. Deployment memerlukan rencana terpisah: backup, migrasi yang diperiksa,
   pengujian staging, waktu penerapan, dan rollback. Merge tidak sama dengan deploy.

Gunakan `feat:`, `fix:`, `docs:`, `test:` atau `chore:` pada pesan commit.
`main` berisi perubahan yang sudah diterima. Tag baseline hanya menandai snapshot,
bukan sertifikasi siap produksi. Riwayat rilis dicatat di `CHANGELOG.md`.

## Tes aplikasi tanpa memakai database produksi

Dari root repository, gunakan virtualenv tersendiri. Jangan memakai Python global
atau menjalankan `docker compose up` dengan nama project produksi.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cd app
PM_SECRET_KEY=isolated-test-only-not-used-in-production PM_HTTPS=0 ../.venv/bin/python manage.py check --settings=config.test_settings
PM_SECRET_KEY=isolated-test-only-not-used-in-production PM_HTTPS=0 ../.venv/bin/python manage.py test maintenance --settings=config.test_settings --noinput
```

Jika dukungan venv belum tersedia, hentikan tahap tes dan gunakan komputer dev;
jangan melakukan upgrade paket server produksi secara otomatis. Tes ini memakai
SQLite sementara; bukan validasi PostgreSQL, beban, Cloudflare, atau seluruh UI.

## Git safety

Script ekspor mengaktifkan hooks pada salinan awal. Setelah clone di perangkat lain:

```bash
git config --local core.hooksPath .githooks
```

Python 3 diperlukan. Guard memeriksa path, pola token tertentu dan, jika tersedia
secara lokal, membandingkan kredensial PM tanpa mencetak atau menyalinnya. Pre-push
memeriksa file pada riwayat commit yang akan dikirim, bukan hanya versi terakhir.
Ini best-effort: review manual tetap wajib, dan hooks dapat dilewati pengguna.
Jangan mengandalkan private repository sebagai tempat penyimpanan password.

Tidak ada workflow auto-deploy, SSH key baru, token GitHub, konfigurasi DNS,
perubahan Cloudflared/Tailscale, atau perubahan layanan lama dalam proses ekspor.
