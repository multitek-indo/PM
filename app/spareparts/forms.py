from django import forms


class SparepartPhotoForm(forms.Form):
    kind = forms.ChoiceField(label='Kondisi sparepart', choices=[('', 'Pilih kondisi'), ('broken', 'Rusak'), ('needed', 'Dibutuhkan')])
    part_name = forms.CharField(label='Nama sparepart', min_length=2, max_length=120,
                                widget=forms.TextInput(attrs={'placeholder': 'Contoh: sensor proximity, bearing, motor servo'}))
    note = forms.CharField(label='Keterangan tambahan (opsional)', max_length=600,
                           required=False, widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Jenis kerusakan atau spesifikasi sparepart yang dibutuhkan'}))
    photo = forms.FileField(label='Foto sparepart', widget=forms.ClearableFileInput(attrs={
        'accept': 'image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp',
    }), help_text='JPG, PNG, atau WEBP; maksimal 6 MB dan 24 megapiksel. Gambar dikompresi dan metadata lokasi dihapus.')

    def clean_photo(self):
        upload = self.cleaned_data['photo']
        if not upload.size or upload.size > 6 * 1024 * 1024:
            raise forms.ValidationError('Foto harus berukuran 1 byte sampai 6 MB.')
        return upload
