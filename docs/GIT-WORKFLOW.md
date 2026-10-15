# Catatan workflow

Contoh branch: `feat/rekap-bulanan`, `fix/checklist-validation`, `docs/panduan-teknisi`.
Satu commit untuk satu perubahan yang dapat dijelaskan dan diuji.
Jangan mengedit source produksi ketika salinan Git juga sedang dikembangkan;
perubahan darurat di produksi harus direkonsiliasi lewat diff, bukan disalin
menimpa branch kerja tanpa pemeriksaan.

GitHub menyimpan kode dan riwayat, bukan state database, password, volume Docker,
file Nextcloud, atau rekaman CCTV. Pengembalian commit tidak otomatis membatalkan
migrasi database. Jangan memakai `git reset --hard`, `git clean -fd`, atau
`git push --force` sebagai solusi umum atas konflik.

Commit email masuk ke metadata Git. Gunakan alamat noreply yang benar-benar
ditampilkan pada Settings > Emails akun GitHub, bukan alamat yang ditebak.

Referensi:
- https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github
- https://docs.github.com/en/get-started/using-github/github-flow
- https://git-scm.com/docs/gitignore
- https://git-scm.com/docs/githooks
