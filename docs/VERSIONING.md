# Versioning dan rilis Multitek PM

## Tiga hal berbeda

**Commit** mencatat perubahan kode. **Tag dan GitHub Release** menandai/menerangkan snapshot kode. **Deployment** menerapkan snapshot itu ke server. Membuat commit, push, atau GitHub Release tidak otomatis mengubah VPS.

Sumber nomor versi hanya `app/VERSION.txt`. Isinya angka tanpa awalan `v`, misalnya `0.3.0`. Tag menambahkan awalan `v`: `v0.3.0`. Runtime membaca file tersebut di dalam aplikasi. Jangan mengubah versi langsung di server hanya agar label berubah: kode yang berjalan harus sama dengan versi yang dirilis.

Kebijakan proyek: patch `0.3.1` untuk perbaikan, minor `0.4.0` untuk fitur baru; `1.0.0` baru setelah kriteria rilis stabil dipenuhi. Versi 0.x masih pengembangan awal. Setelah 1.0, perubahan kompatibilitas besar mengikuti kenaikan major. Jangan menggunakan ulang atau memindahkan tag versi yang sudah dirilis. Baseline bertanggal dari paket sebelumnya tetap menjadi catatan historis.

## Mengedit melalui GitHub

1. Buat branch pendek, contohnya `fix/validasi-identitas`, bukan mengedit kode produksi.
2. Ubah hanya fitur yang diminta. Pada perubahan yang akan dirilis, naikkan `app/VERSION.txt` (contoh `0.3.1`).
3. Buat `docs/releases/0.3.1.md`: ringkasan perubahan, cara verifikasi, dampak database, hasil tes, dan langkah pemulihan. Jangan memuat password atau data pelanggan.
4. Buat Pull Request ke main, periksa diff dan jalankan pengujian dalam lingkungan development. Setelah hasil sesuai, merge.
5. Di checkout development VPS, pastikan tidak ada perubahan lokal sebelum mengambil update. Jangan menjalankan `git pull` pada `/opt/multitek-pm`.

```bash
cd /home/multitek/projects/multitek-pm &&
git status --short &&
git pull --ff-only origin main &&
python3 tools/pm_release.py check &&
python3 tools/pm_release.py tag
```

`git status` hanya menampilkan perubahan, tidak menghentikan shell. Jika ada output perubahan, hentikan dan selesaikan dulu. Helper `tag` juga menolak working tree kotor, branch selain main, remote tidak sesuai, main lokal berbeda, atau tag lama yang akan tertimpa. `git pull --ff-only` tidak menghapus perubahan atau menyelesaikan konflik otomatis. Tidak memakai force push.

Untuk satu pemeriksaan yang benar-benar menghentikan langkah berikut ketika ada perubahan lokal:

```bash
bash <<'SH'
set -Eeuo pipefail
cd /home/multitek/projects/multitek-pm
[ -z "$(git status --porcelain=v1 --untracked-files=all)" ] || {
    echo 'STOP: ada perubahan lokal; tidak pull/tag.' >&2; exit 1;
}
[ "$(git branch --show-current)" = main ] || {
    echo 'STOP: checkout bukan main.' >&2; exit 1;
}
git pull --ff-only origin main
python3 tools/pm_release.py check
python3 tools/pm_release.py tag
SH
```

## Membuat halaman Release di GitHub

Di repository `multitek-indo/PM`: **Releases > Draft a new release > Choose a tag**. Pilih tag yang SUDAH DIBUAT helper (contoh `v0.3.1`); jangan membuat tag baru pada commit yang belum diperiksa. Judul `Multitek PM v0.3.1`. Salin isi catatan versi yang sesuai dari `docs/releases/0.3.1.md`. Tandai pre-release bila masih pilot. Klik Publish release setelah review.

Tidak diperlukan token GitHub baru di VPS untuk proses tag: memakai SSH/core.sshCommand repository yang sudah ada. Halaman Release dibuat lewat sesi web GitHub Anda. Script upgrade 0.3.0 hanya push commit + tag, tidak mengklaim membuat halaman Release melalui API.

## Menguji sebelum merilis

Gunakan Python virtualenv development atau container terisolasi, bukan `compose up` produksi. Ikuti panduan development yang sudah ada. Jalankan suite baru DAN lama:

```bash
cd /home/multitek/projects/multitek-pm/app
PM_SECRET_KEY=isolated-development-test-only PM_HTTPS=0 \
  ../.venv/bin/python manage.py test maintenance branding \
  --settings=config.test_settings --noinput
```

Perintah mengasumsikan `.venv` development sudah disiapkan. Jika belum ada, jangan menginstal library global server secara otomatis. SQLite sementara tidak menggantikan uji PostgreSQL atau uji beban. Migrasi harus diperiksa pada salinan database sebelum produksi.

## Deployment setelah rilis berikutnya

Paket upgrade 0.3.0 khusus perubahan identitas/versioning ini, **bukan installer generik untuk semua commit mendatang**. Jangan menjalankannya lagi untuk menerapkan fitur 0.3.1/0.4.0 yang berbeda. Deploy berikutnya perlu paket/rencana sesuai diff-nya: backup, uji restore, tes kode, review migrasi, jendela pemeliharaan, health check, dan rollback kode yang kompatibel. Jangan checkout tag langsung pada source bind-mount produksi.

Lokasi source produksi `/opt/multitek-pm`; folder Git `/home/multitek/projects/multitek-pm`. GitHub tidak berisi `.env`, dump database, nama perusahaan yang disimpan di DB, ataupun kunci SSH. Instalasi perusahaan lain memakai instance/database terpisah dan pengaturan nama melalui admin, bukan mengganti data perusahaan pertama.

## File versioning yang relevan

- `app/VERSION.txt`: satu nomor rilis runtime.
- `app/config/version.py`: parser versi.
- `app/config/settings.py`: mengimpor nomor tersebut, tetap mempertahankan konfigurasi HTTPS lama.
- `app/branding/context_processors.py`: menyalurkan versi/nama ke template.
- `app/maintenance/views.py`: health menampilkan versi dari settings, alur lain tetap.
- `tools/pm_release.py`: validasi dan push tag, tanpa deployment.
- `docs/releases/<versi>.md`: catatan tiap versi, tidak menimpa catatan lama.

## Referensi resmi

- SemVer: https://semver.org/
- GitHub Releases: https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository
- Git tag: https://git-scm.com/docs/git-tag
- Git push: https://git-scm.com/docs/git-push
