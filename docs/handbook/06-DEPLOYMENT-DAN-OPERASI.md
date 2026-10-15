# 06 - Deployment dan operasi yang tidak mengganggu layanan lama

[Kembali ke indeks](README.md)

## 1. Perbedaan commit dan deployment

Dokumentasi/README saja: commit dan push; tidak ada alasan me-restart aplikasi.
Template/CSS/kode Python: perlu penerapan file yang dipilih dan verifikasi web.
Perubahan model: perlu migrasi yang diperiksa. Perubahan dependensi: perlu
menyiapkan paket runtime yang cocok; mengubah requirements di Git saja tidak
mengubah volume `/packages` pada produksi.

Paket ini bukan auto-deployer. Belum ada release pipeline atomik maupun staging
siap pakai; jangan menyalin satu perintah reset/pull sebagai pengganti proses
rilis. Rujukan eksternal: [Django deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/).

## 2. Checklist sebelum menyentuh produksi

1. Commit/tag target jelas, review selesai, tes dev lulus, PostgreSQL staging
   lulus untuk perubahan skema/konkurensi, dan kode darurat di produksi direkonsiliasi.
2. Backup database PM, konfigurasi privat, kode runtime, dan daftar dependensi
   tersedia serta pernah diuji pemulihannya. Salinan di disk yang sama bukan
   perlindungan terhadap kegagalan disk/VM.
3. Tentukan downtime PM, siapa pengguna terdampak, migrasi forward/rollback,
   batas waktu penghentian proses, dan pemeriksaan layanan lama.
4. Pastikan path/Compose target hanya `/opt/multitek-pm`; Nextcloud, Odoo, CCTV,
   Tor, Portainer, Cloudflared, dan Tailscale tidak menjadi sasaran restart.

Backup belum dibuktikan selesai oleh log instalasi yang mendasari dokumentasi.
Jangan menyatakan backup 'aman' hanya karena command dump berakhir tanpa error.

## 3. Pemeriksaan read-only terarah

```bash
bash /opt/multitek-pm/pmctl status
curl --noproxy '*' --connect-timeout 3 --max-time 10 http://127.0.0.1:18080/healthz
```

Health `status=ok` berarti koneksi SELECT 1 berhasil, bukan audit semua transaksi.
Untuk ringkasan layanan bersama gunakan satu blok berikut; hindari mencetak env
container atau command line cloudflared karena dapat berisi token:

```bash
printf '\n=== PM ===\n'
bash /opt/multitek-pm/pmctl status
printf '\n=== CONTAINER LAIN ===\n'
docker ps --format 'table {{.Names}}	{{.Status}}	{{.Ports}}'
printf '\n=== NEXTCLOUD ===\n'
snap services nextcloud
printf '\n=== AKSES ===\n'
systemctl is-active cloudflared tailscaled || true
printf '\n=== KAPASITAS ===\n'
df -h /
free -h
```

`pmctl logs` membaca 100 baris log tiap service PM. Periksa lokal dan redaksi data
sensitif sebelum dibagikan. Jangan mengirim full inspect/environment ke chat.

## 4. Backup: cakupan yang harus ada

| Komponen | Metode/hasil yang dibutuhkan |
|---|---|
| PostgreSQL PM | Logical dump konsisten, file tidak kosong, restore ke database terisolasi dan cek jumlah/relasi data |
| Source runtime | Arsip kode yang benar-benar terpasang, identitas commit atau manifest hash |
| Konfigurasi privat | .env dan konfigurasi penting dalam penyimpanan terenkripsi, akses terbatas; bukan Git |
| Dependensi | Image ID dan daftar versi dalam packages; paket ulang harus diuji |
| Infrastruktur | Rencana backup VM/datastore dan salinan di lokasi lain |

Contoh pembuatan dump berikut adalah **operasi backup yang menghasilkan I/O**,
bukan pemeriksaan read-only. Jalankan hanya pada waktu disepakati, setelah ruang
cukup dan backup tujuan ditentukan. Ini tidak melakukan restore atau restart:

```bash
(
  set -euo pipefail
  umask 077
  DEST="$(mktemp -d /root/multitek-pm-db-backup.XXXXXXXX)"
  docker compose --project-directory /opt/multitek-pm     -p multitek-pm -f /opt/multitek-pm/compose.yaml     --env-file /opt/multitek-pm/.env     exec -T db pg_dump -U pm_owner -d multitek_pm -Fc > "$DEST/database.dump"
  test -s "$DEST/database.dump"
  sha256sum "$DEST/database.dump" > "$DEST/SHA256SUMS"
  printf 'Dump lokal dibuat: %s\nBelum membuktikan restore atau backup off-site.\n' "$DEST"
)
```

Akses database harus tetap sesuai konfigurasi server; bila authentication ditolak,
jangan mengubah pg_hba.conf agar command lolos. Backup ini belum mencakup
Nextcloud/Odoo atau konfigurasi privat. Jangan upload folder tersebut ke GitHub.

## 5. Urutan rilis yang disarankan

Ambil snapshot baseline layanan -> arsipkan runtime/config -> dump database ->
siapkan source release yang sudah direview -> cek diff termasuk patch HTTPS ->
terapkan dalam jendela maintenance PM -> migrasi bila perlu -> nyalakan ulang
hanya service PM yang berubah -> uji aplikasi dan layanan lama -> catat hasil.

Jangan menjalankan installer awal/bootstrap untuk memperbarui aplikasi.
`pm_bootstrap` menolak admin yang sudah ada, dan database init script tidak
berjalan ulang pada volume PostgreSQL lama.

Untuk perubahan aplikasi yang memang siap diterapkan, operator dapat memakai
Compose dengan `--project-directory`, `-p`, `-f`, dan `--env-file` eksplisit.
`up --no-deps` membatasi service yang disentuh; penggunaan flag tersebut tidak
menggantikan backup atau menjamin tidak ada jeda pada web PM. Lihat
[Docker Compose up](https://docs.docker.com/reference/cli/docker/compose/up/).

Dokumen ini sengaja tidak menyajikan perintah penyalinan seluruh repo ke produksi:
repo tidak membawa .env/private/packages, dan menimpa seluruh direktori dapat
menghilangkan konfigurasi runtime. Buat prosedur deployment spesifik untuk diff
yang benar-benar akan dirilis.

## 6. Verifikasi sesudah deployment

Periksa health database, login melalui jalur aktual, cookie/CSRF, tampilan CSS,
WO sesuai akses, submit/review data uji terkendali, scheduler heartbeat, serta
status/container ID/start-time layanan lama. HTTP 200 dari halaman login saja
belum membuktikan fungsi pekerjaan berjalan.

Untuk Cloudflare, lihat hostname final pada konfigurasi privat sendiri. Jangan
mengganti Host menjadi localhost untuk mengatasi 400, menonaktifkan CSRF untuk
403, atau membuka port 18080 ke semua interface untuk mengatasi 502.

## 7. Rollback

Rollback kode membutuhkan salinan release sebelumnya. Rollback migrasi tidak
selalu aman/tersedia: penghapusan kolom atau transformasi data bisa kehilangan
informasi. Review reverse migration dan rencana restore sebelum rilis, bukan
ketika insiden sudah terjadi. `git revert` membuat commit pembalikan kode;
bukan otomatis mengembalikan database.

Untuk masalah pada PM, penghentian terarah tersedia lewat
`bash /opt/multitek-pm/pmctl stop`. Ini memengaruhi PM; jangan menggunakannya
sebagai langkah rutin setiap kali mengubah dokumentasi. Jangan gunakan `docker
compose down -v`, volume prune, atau reset seluruh host.
