from decimal import Decimal, InvalidOperation
from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from maintenance.services import visible_orders
from .models import Part, PartRequest, Stocktake


def positive_number(value):
    if value is None or not value.is_finite() or value <= 0:
        raise ValidationError('Jumlah harus lebih besar dari nol.')
    return value


class PartForm(forms.ModelForm):
    min_qty = forms.IntegerField(label='Stok minimum', min_value=0, max_value=999999999,
                                 widget=forms.NumberInput(attrs={'step':'1','inputmode':'numeric'}))
    class Meta:
        model = Part
        fields = ['sku', 'name', 'machine_type', 'unit', 'location', 'min_qty', 'active']
        widgets = {'sku': forms.TextInput(attrs={'autocomplete': 'off'}),
                   'machine_type': forms.TextInput(attrs={'placeholder': 'Contoh: mesin jahit high speed'}),
                   'location': forms.TextInput(attrs={'placeholder': 'Contoh: Rak A-03'})}
    def clean_sku(self):
        return self.cleaned_data['sku'].strip().upper()

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if not name:
            raise ValidationError('Nama sparepart wajib diisi.')
        return name


class MovementForm(forms.Form):
    part = forms.ModelChoiceField(queryset=Part.objects.filter(active=True), label='Sparepart')
    kind = forms.ChoiceField(choices=[('receive', 'Barang masuk'), ('issue', 'Barang keluar')], label='Jenis')
    quantity = forms.IntegerField(label='Jumlah', min_value=1, max_value=999999999,
                                  widget=forms.NumberInput(attrs={'step':'1','inputmode':'numeric'}))
    note = forms.CharField(label='Referensi / alasan', max_length=600, widget=forms.Textarea(attrs={'rows':2}))

    def clean_note(self):
        value = self.cleaned_data['note'].strip()
        if not value:
            raise ValidationError('Masukkan nomor dokumen atau alasan mutasi.')
        return value


class RequestForm(forms.ModelForm):
    quantity = forms.IntegerField(label='Jumlah', min_value=1, max_value=999999999,
                                  widget=forms.NumberInput(attrs={'step':'1','inputmode':'numeric'}))
    class Meta:
        model = PartRequest
        fields = ['part', 'quantity', 'order', 'note']
        widgets = {'note': forms.Textarea(attrs={'rows':3, 'placeholder':'Alasan kebutuhan dan kondisi mesin'})}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['part'].queryset = Part.objects.filter(active=True)
        self.fields['order'].required = False
        self.fields['order'].empty_label = 'Tanpa work order'
        self.fields['order'].queryset = (visible_orders(user).filter(status='open') if user and user.is_active
                                          else visible_orders_placeholder())


def visible_orders_placeholder():
    from maintenance.models import WorkOrder
    return WorkOrder.objects.none()


class DecisionForm(forms.Form):
    action = forms.ChoiceField(choices=[('approve', 'Setujui'), ('reject', 'Tolak')])
    note = forms.CharField(required=False, max_length=600, widget=forms.Textarea(attrs={'rows':2}))

    def clean(self):
        data = super().clean()
        if data.get('action') == 'reject' and not (data.get('note') or '').strip():
            raise ValidationError('Alasan penolakan wajib diisi.')
        return data


class StocktakeForm(forms.ModelForm):
    class Meta:
        model = Stocktake
        fields = ['title']
    def clean_title(self):
        return self.cleaned_data['title'].strip()


class CountForm(forms.Form):
    counted_qty = forms.IntegerField(label='Stok fisik', min_value=0, max_value=999999999,
                                     widget=forms.NumberInput(attrs={'step':'1','inputmode':'numeric'}))
