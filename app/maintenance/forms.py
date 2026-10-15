from django import forms
class ImportForm(forms.Form):
    file = forms.FileField(label='CSV UTF-8 master mesin (maksimal 2 MB / 5.000 baris)')
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
