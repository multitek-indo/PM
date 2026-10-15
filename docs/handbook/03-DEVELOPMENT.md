# 03 - Panduan development dari perubahan sampai GitHub

[Kembali ke indeks](README.md)

## 1. Aturan dasar

Kerjakan kode di `/home/multitek/projects/multitek-pm`, bukan
`/opt/multitek-pm`. Gunakan akun Linux yang telah berhasil mengakses repository;
pada proses awal pengguna memakai root. Jangan memindahkan/mengganti private key
agar masalah izin terlihat selesai. Koneksi Git memakai konfigurasi SSH lokal
repository yang sudah disimpan oleh script penghubung.

Setiap perubahan dimulai dari tujuan dan kriteria lulus. Contoh: 'tambahkan
pencarian berdasarkan merek; user tetap tidak boleh melihat WO orang lain'.
Pisahkan perubahan tampilan, aturan bisnis, dan migrasi ke pekerjaan kecil.

## 2. Pemeriksaan awal dalam satu blok

```bash
cd /home/multitek/projects/multitek-pm &&
pwd &&
git status --short &&
git branch --show-current &&
git remote -v &&
git log -1 --oneline &&
python3 --version
```

Pastikan path benar, remote menuju `multitek-indo/PM`, dan Anda memahami seluruh
perubahan yang ditampilkan. Jika working tree tidak bersih, selesaikan perubahan
itu dahulu. Jangan memakai `git reset --hard` atau `git clean` untuk merapikan
pekerjaan yang belum diperiksa.

## 3. Branch untuk satu fitur

Dengan working tree bersih:

```bash
git switch main &&
git pull --ff-only origin main &&
git switch -c feat/pencarian-merek
```

Jika `--ff-only` menolak karena riwayat bercabang, berhenti dan review graph
commit; jangan force push. Untuk perbaikan gunakan `fix/...`, untuk dokumentasi
`docs/...`. Nama branch menunjukkan tujuan, bukan nama orang.

## 4. Siapkan Python terpisah

Pada root checkout Git, bukan shell di container produksi:

```bash
python3 -m venv .venv &&
.venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt
```

Tidak ada `sudo pip`, `apt upgrade`, atau instalasi ke Python global. Jika `venv`
atau dependensi tidak tersedia, berhenti: sediakan lingkungan developer/VM
terpisah sebelum memasang paket OS pada VPS bersama. Versi paket sebagian berupa
rentang, sehingga hasil instalasi baru dapat berbeda dari volume package
produksi; catat `pip freeze` pada bukti tes, jangan menyebutnya identik tanpa cek.

## 5. Jalankan tes baseline

Perintah berikut memakai SQLite sementara dan bukan konfigurasi database
produksi. `PM_SECRET_KEY` di sini hanya nilai sementara untuk proses tes.

```bash
(
  set -e
  cd /home/multitek/projects/multitek-pm
  export PM_SECRET_KEY="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(48))')"
  export PM_HTTPS=0
  unset PM_PUBLIC_BASE_URL PM_CSRF_ORIGINS
  .venv/bin/python app/manage.py check --settings=config.test_settings
  .venv/bin/python app/manage.py makemigrations --check --dry-run --settings=config.test_settings
  .venv/bin/python app/manage.py test maintenance --settings=config.test_settings --noinput --verbosity=2
)
```

Jangan menyalin `.env` produksi atau `private/bootstrap.env` untuk menjalankan tes.
Output yang diharapkan: pemeriksaan sistem lolos, tidak ada migrasi tertinggal,
dan tes berakhir `OK`. Pada source baseline ada 33 test method. Angka itu bukan
bukti seluruh kombinasi perilaku telah teruji.

## 6. Preview UI dengan database DEV yang bertahan

`config.test_settings` memakai database in-memory dan hasher cepat untuk tes;
**jangan gunakan untuk menyimpan data preview atau menjalankan server publik**.
Contoh baru [examples/dev_settings.py](examples/dev_settings.py) memakai SQLite
terpisah di `~/.local/share/multitek-pm-dev`, secret dev terpisah, serta tidak
memakai password database produksi. Ini alat developer, bukan fitur runtime.

Dari root checkout, di sesi SSH biasa:

```bash
export PYTHONPATH="$PWD/docs/handbook/examples:$PWD/app"
.venv/bin/python app/manage.py check --settings=dev_settings &&
.venv/bin/python app/manage.py migrate --settings=dev_settings --noinput
```

Untuk pertama kali, buat admin dev dan grup dengan password yang Anda input
sendiri. Tidak tampil di layar dan tidak dicatat dalam Git:

```bash
read -r -s -p "Password admin DEV (minimal 12 karakter): " PM_ADMIN_PASSWORD
printf '\n'
export PM_ADMIN_PASSWORD
.venv/bin/python app/manage.py pm_bootstrap --settings=dev_settings
unset PM_ADMIN_PASSWORD
```

Bootstrap akan menolak bila admin sudah ada; jangan menghapus database untuk
mengatasinya. Gunakan akun dev yang telah dibuat. Buat beberapa mesin uji dan
akun berbeda untuk menguji verifikasi.

Periksa port sebelum preview, lalu jalankan server hanya pada loopback:

```bash
ss -lnt '( sport = :18081 )'
.venv/bin/python app/manage.py runserver 127.0.0.1:18081 --settings=dev_settings
```

Jika port telah digunakan, jangan mematikan layanan pemiliknya. Pilih port lain
yang kosong dan sesuaikan forwarding. Pada CMD Windows terpisah:

```cmd
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:18081:127.0.0.1:18081 root@100.123.222.1
```

Buka `http://127.0.0.1:18081` di PC tersebut. Jangan membuat rute Cloudflare untuk
runserver. Penghentian dengan Ctrl+C hanya menghentikan preview ini.

Scheduler dev tidak otomatis berjalan bersama runserver. Setelah membuat Plan,
pada shell kedua root checkout jalankan:

```bash
export PYTHONPATH="$PWD/docs/handbook/examples:$PWD/app"
.venv/bin/python app/manage.py pm_scheduler --once --settings=dev_settings
```

Ini membuat WO pada **database DEV**. Jangan menghapus argumen `--settings`.
QR dev sengaja dinonaktifkan; pengujian QR HTTP dilakukan melalui test suite
atau staging HTTPS, bukan dengan mencetak label localhost untuk lapangan.

## 7. Contoh perubahan paling aman: pencarian merek

Pada `app/maintenance/views.py`, fungsi `machines`, tambahkan pencarian
`manufacturer__icontains=q` pada gabungan `Q(...)` yang sudah ada. Jangan
menghapus pembatas panjang pencarian atau pagination. Sesuaikan placeholder
`app/templates/machines.html` agar pengguna mengetahui merek dapat dicari.

Tambahkan test pada `PMTests` di `app/maintenance/tests.py`. Ikuti pola login dan
fixture yang sudah digunakan; buat dua mesin dengan merek berbeda, cari salah
satu, dan pastikan hanya mesin yang cocok ditampilkan. Tidak diperlukan migrasi
untuk perubahan filter atas kolom yang sudah ada.

Lihat hasil di dev, jalankan seluruh tes, kemudian review `git diff`. Jangan
menambahkan pembacaan variabel password ke log untuk debugging.

## 8. Contoh perubahan struktur: kolom kode aset tambahan

Ini resep perubahan, bukan fitur yang sudah tersedia. Misalnya ingin
`asset_tag` opsional pada Machine. Tambahkan field dengan `blank=True` agar
migrasi tidak memerlukan nilai rekaan untuk seluruh data lama. Tentukan apakah
kode perlu unik; jangan langsung memasang unique pada data yang belum diperiksa.

Urutan berkas: `models.py` -> `admin.py` -> `machine.html`/`machines.html` ->
`views.py` bila ingin pencarian -> `importing.py` bila masuk CSV -> tests ->
migrasi -> manual. Perubahan FIELDS bisa mematahkan CSV lama; tentukan apakah
kolom baru opsional atau revisi format diberi versi.

Di lingkungan DEV dari langkah 6:

```bash
.venv/bin/python app/manage.py makemigrations maintenance --name machine_asset_tag --settings=dev_settings
.venv/bin/python app/manage.py migrate --plan --settings=dev_settings
.venv/bin/python app/manage.py migrate --settings=dev_settings --noinput
```

Baca file migrasi yang dihasilkan. Gunakan `sqlmigrate` dengan nama migrasi aktual
untuk meninjau SQL bila diperlukan. Test pada PostgreSQL staging sebelum produksi;
SQLite tidak membuktikan perilaku lock PostgreSQL. Commit model dan migrasinya
bersama. Jangan mengubah `0001_initial.py` yang telah diterapkan.

## 9. Simpan dan kirim perubahan

```bash
git diff --check &&
git diff --stat &&
git status --short
```

Pilih file yang berkaitan dengan kebutuhan; contoh perubahan pencarian:

```bash
git add app/maintenance/views.py app/templates/machines.html app/maintenance/tests.py &&
git diff --cached --stat &&
git commit -m "feat: tambah pencarian mesin berdasarkan merek" &&
git push -u origin feat/pencarian-merek
```

Perbarui manual dan CHANGELOG bila perilaku berubah, lalu sertakan pada commit
yang relevan. Jangan menggunakan `git add .` dari direktori induk server.

Di GitHub buat Pull Request `feat/pencarian-merek -> main`: tulis tujuan, file,
hasil tes, dampak data, serta rencana deployment/rollback. Lakukan review meski
bekerja sendiri. Setelah merge, salinan produksi tetap versi lama sampai
[prosedur deployment](06-DEPLOYMENT-DAN-OPERASI.md) dilaksanakan.

## 10. Clone pada komputer lain

Clone kode tidak membawa konfigurasi SSH lokal repository maupun virtualenv.
Perangkat baru perlu akses GitHub sendiri yang disetujui dan identitas commit.
Aktifkan ulang hook di checkout baru:

```bash
git config --local core.hooksPath .githooks
```

Kunci privat tidak boleh ikut repository. Panduan alur branch merujuk
[GitHub flow](https://docs.github.com/en/get-started/using-github/github-flow);
penjelasan migrasi merujuk [Django migrations](https://docs.djangoproject.com/en/5.2/topics/migrations/).
