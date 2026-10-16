# Pengaturan nama perusahaan dan hak akses

## Batas fitur

Nama bawaan **Multitek Indonesia**. Fitur ini hanya mengganti identitas yang terlihat pada halaman aplikasi. Nama produk **Multitek PM / Smart Maintenance**, domain, repository, folder, container, database, data mesin dan work order tidak diubah.

Satu nama perusahaan berlaku untuk SELURUH instalasi, bukan nama yang berbeda per grup. Ini bukan sistem multi-tenant: bila dipakai oleh dua pelanggan berbeda, gunakan instalasi/database terpisah. Mengganti nama perusahaan pada satu server tidak memisahkan data lama dan baru. Nama pada halaman login terlihat sebelum login; gunakan identitas perusahaan yang memang boleh ditampilkan.

## Mengganti nama sebagai administrator

1. Masuk dengan akun superuser/admin Anda.
2. Buka **Administrasi > Identitas perusahaan > Buka daftar**.
3. Klik baris **Multitek Indonesia**.
4. Ubah **Nama perusahaan** dan klik **Simpan**.
5. Muat ulang dashboard/login/admin: nama baru berlaku untuk seluruh pengguna tanpa restart.

Nama wajib diisi, maksimum 120 karakter. Spasi luar dibuang, karakter kontrol ditolak, teks pada HTML di-escape. Tidak perlu memasukkan logo, alamat, kontak, maupun domain: kolom tersebut memang tidak ditambahkan pada rilis ini. Hanya ada satu profil; tombol tambah/hapus dinonaktifkan. Perubahan dari admin tercatat pada riwayat perubahan admin Django.

## Memberikan akses kepada pengguna lain

Grup baru **Pengelola Identitas Perusahaan** mempunyai tepat dua permission:

| Label pada hak akses | Kode backend | Efek |
|---|---|---|
| Dapat melihat nama perusahaan | `branding.view_companyprofile` | Dapat membuka data secara read-only pada admin. |
| Dapat mengubah nama perusahaan | `branding.change_companyprofile` | Dapat menyimpan nama baru. |

Grup ini TIDAK otomatis dimasukkan ke akun siapa pun, tidak memberikan izin mesin/jadwal/pengguna/grup lain, dan tidak mengubah Supervisor PM atau Teknisi PM.

Untuk memberikan kemampuan tersebut: **Administrasi > Pengguna > pilih akun > Grup** lalu tambahkan grup Pengelola Identitas Perusahaan. Akun harus **Aktif** dan **Status staf** untuk mengakses admin. Jangan mengaktifkan Status superuser hanya untuk mengubah nama perusahaan; itu memberikan semua izin.

Alternatif sesuai contoh screenshot: buka **Administrasi > Grup > Supervisor PM**, cari `nama perusahaan`, lalu pindahkan dua permission di atas ke hak akses terpilih. Klik Simpan. Langkah ini dilakukan sendiri oleh admin bila memang semua supervisor boleh mengubah identitas; paket tidak melakukannya otomatis.

Untuk akses baca saja, buat grup sendiri dengan hanya permission melihat. Untuk mencabut, hapus permission/keanggotaan yang sesuai. Hak yang diberikan melalui grup lain atau langsung pada pengguna tetap berlaku sampai dicabut juga. Akun superuser aktif tetap memiliki semua permission sesuai mekanisme Django.

## Pemulihan dan pengembangan

Nama disimpan di tabel baru `branding_companyprofile`, bukan di file source. Upgrade kode selanjutnya tidak perlu dan tidak boleh mengganti nama yang sudah disetel. Migrasi pertama mengisi default sekali; restart tidak menjalankan seed lagi. Jangan memanggil initializer/bootstrap lama untuk mereset identitas atau grup.

File utama: `app/branding/models.py`, `admin.py`, `context_processors.py`, `apps.py`, `migrations/0001_initial.py`, dan `tests.py`. Registrasi app/context processor ditambahkan di akhir settings; hanya label identitas/version diganti pada tiga template yang sudah ada. CSS dan JS tidak disentuh.

Jika gagal deploy setelah migrasi sukses, pemulihan otomatis mengembalikan source lama tanpa menghapus tabel/grup baru. Ini sengaja mempertahankan data. Memutar mundur kode bukan berarti memutar mundur database. Jangan `migrate branding zero` atau restore dump tanpa rencana pemulihan dan persetujuan.

Referensi: https://docs.djangoproject.com/en/5.2/topics/auth/default/#permissions-and-authorization
