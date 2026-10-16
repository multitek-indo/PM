from django import forms
from .models import Machine


class MachineEditForm(forms.ModelForm):
    class Meta:
        model = Machine
        fields = ['code','name','category','manufacturer','model','serial','site','line','active','notes']
        widgets = {'notes':forms.Textarea(attrs={'rows':3})}
