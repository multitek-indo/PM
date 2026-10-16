from django.conf import settings
from django.db import models
from django.core.validators import MinLengthValidator
from maintenance.models import WorkOrder


class SparepartPhoto(models.Model):
    KINDS = [('broken', 'Sparepart rusak'), ('needed', 'Sparepart dibutuhkan')]
    order = models.ForeignKey(WorkOrder, on_delete=models.PROTECT, related_name='sparepart_photos')
    kind = models.CharField('Keterangan kondisi', max_length=8, choices=KINDS)
    part_name = models.CharField('Nama sparepart', max_length=120, validators=[MinLengthValidator(2)])
    note = models.CharField('Catatan teknisi', max_length=600, blank=True)
    filename = models.CharField(max_length=36, unique=True, editable=False)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        verbose_name = 'Foto sparepart'
        verbose_name_plural = 'Foto sparepart'

    def __str__(self):
        return f'{self.order} - {self.part_name}'
