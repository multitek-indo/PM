from django.core.exceptions import ValidationError
from django.db import models
import unicodedata

DEFAULT_COMPANY_NAME = 'Multitek Indonesia'


class CompanyProfile(models.Model):
    # Only one company identity per installation. Not a multi-tenant boundary.
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    company_name = models.CharField('Nama perusahaan', max_length=120, default=DEFAULT_COMPANY_NAME,
        help_text='Identitas yang tampil pada aplikasi. Tidak mengubah nama produk, mesin, database, atau domain.')
    updated_at = models.DateTimeField('Terakhir diperbarui', auto_now=True)

    class Meta:
        verbose_name = 'Identitas perusahaan'
        verbose_name_plural = 'Identitas perusahaan'
        default_permissions = ()
        permissions = [
            ('view_companyprofile', 'Dapat melihat nama perusahaan'),
            ('change_companyprofile', 'Dapat mengubah nama perusahaan'),
        ]
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name='pm_company_single_row')]

    def __str__(self):
        return self.company_name

    def clean(self):
        super().clean()
        self.company_name = self.company_name.strip()
        if not self.company_name or any(unicodedata.category(c).startswith('C') for c in self.company_name):
            raise ValidationError({'company_name': 'Isi nama perusahaan tanpa karakter kontrol.'})
        if self.pk != 1:
            raise ValidationError('Hanya satu identitas perusahaan per instalasi.')

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
