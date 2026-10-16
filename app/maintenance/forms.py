from django import forms
class ImportForm(forms.Form):
    file = forms.FileField(label='Pilih Excel (.xlsx) atau CSV (.csv)', widget=forms.ClearableFileInput(attrs={'accept':'.xlsx,.csv'}), help_text='Excel maksimal 5 MiB; CSV 2 MiB. Maksimal 5.000 baris data.')
    sheet_name = forms.CharField(label='Nama sheet Excel (opsional)', required=False, max_length=31, help_text='Kosongkan untuk memakai sheet Mesin, atau sheet terlihat pertama. CSV mengabaikan isian ini.')
    def clean_file(self):
        f = self.cleaned_data['file']
        suffix = f.name.rsplit('.',1)[-1].lower() if '.' in f.name else ''
        if suffix not in ('xlsx','csv'):
            raise forms.ValidationError('Gunakan .xlsx atau .csv. Untuk .xls/.xlsm, Save As menjadi .xlsx tanpa macro; tidak perlu mengubahnya ke CSV.')
        limit = (5 if suffix == 'xlsx' else 2) * 1024 * 1024
        if f.size > limit:
            raise forms.ValidationError('Ukuran file melebihi batas format yang dipilih.')
        return f
class ChecklistForm(forms.Form):
    notes = forms.CharField(label='Temuan / tindakan / catatan',required=False,max_length=4000,widget=forms.Textarea(attrs={'rows':4}))
    def __init__(self,*args,items,**kwargs):
        super().__init__(*args,**kwargs)
        for i,item in enumerate(items):
            self.fields[f'item_{i}'] = forms.ChoiceField(label=item,choices=[('','Pilih hasil'),('ok','Normal / sesuai pemeriksaan'),('fail','Tidak normal / perlu tindak lanjut')])
        self.order_fields([f'item_{i}' for i in range(len(items))]+['notes'])
class ReviewForm(forms.Form):
    decision = forms.ChoiceField(label='Keputusan',choices=[('approve','Setujui pekerjaan'),('reject','Kembalikan ke teknisi')])
    note = forms.CharField(label='Catatan supervisor (wajib untuk pengembalian)',required=False,max_length=2000,widget=forms.Textarea(attrs={'rows':3}))

from django.contrib.auth import get_user_model
class AssignmentForm(forms.Form):
    technician = forms.ModelChoiceField(label='Teknisi aktif',queryset=get_user_model().objects.filter(is_active=True).order_by('username'))
