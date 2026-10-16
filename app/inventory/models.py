"""Single-store sparepart ledger, requests and snapshot-based physical stocktake.

This is intentionally separate from maintenance scheduling/checklist/audit models.
"""
from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from maintenance.models import WorkOrder

ZERO = Decimal('0.000')
LIMIT = Decimal('999999999.999')


class Part(models.Model):
    UNITS = [('pcs', 'Pcs'), ('set', 'Set'), ('meter', 'Meter'),
             ('liter', 'Liter'), ('roll', 'Roll'), ('other', 'Lainnya')]
    sku = models.CharField('Kode sparepart', max_length=64, unique=True)
    name = models.CharField('Nama sparepart', max_length=160)
    machine_type = models.CharField('Jenis/tipe mesin', max_length=120, blank=True)
    unit = models.CharField('Satuan', max_length=8, choices=UNITS, default='pcs')
    location = models.CharField('Lokasi penyimpanan', max_length=120, blank=True)
    current_qty = models.DecimalField('Stok tersedia', max_digits=12, decimal_places=3, default=ZERO,
                                      validators=[MinValueValidator(ZERO)])
    min_qty = models.DecimalField('Batas minimum', max_digits=12, decimal_places=3, default=ZERO,
                                  validators=[MinValueValidator(ZERO)])
    active = models.BooleanField('Aktif', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sku']
        verbose_name = 'Master sparepart'
        verbose_name_plural = 'Master sparepart'
        constraints = [models.CheckConstraint(condition=Q(current_qty__gte=0), name='inv_qty_nonnegative'),
                       models.CheckConstraint(condition=Q(min_qty__gte=0), name='inv_min_nonnegative')]

    def __str__(self):
        return f'{self.sku} - {self.name}'


class PartRequest(models.Model):
    STATUS = [('pending', 'Menunggu'), ('approved', 'Disetujui'),
              ('rejected', 'Ditolak'), ('fulfilled', 'Sudah dikeluarkan')]
    part = models.ForeignKey(Part, on_delete=models.PROTECT, related_name='requests')
    order = models.ForeignKey(WorkOrder, on_delete=models.PROTECT, blank=True, null=True,
                              related_name='inventory_requests')
    quantity = models.DecimalField('Jumlah diminta', max_digits=12, decimal_places=3,
                                   validators=[MinValueValidator(Decimal('0.001'))])
    note = models.CharField('Keterangan kebutuhan', max_length=600, blank=True)
    status = models.CharField(max_length=12, choices=STATUS, default='pending', db_index=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                     related_name='sparepart_requests')
    created_at = models.DateTimeField(auto_now_add=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.PROTECT, related_name='sparepart_decisions')
    decided_at = models.DateTimeField(null=True, blank=True)
    manager_note = models.CharField(max_length=600, blank=True)
    approval_route = models.CharField('Jalur persetujuan', max_length=12, choices=[('stock_admin','Admin sparepart'),('manager','Manager sparepart')], default='stock_admin')
    fulfilled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.PROTECT, related_name='sparepart_fulfillments')
    fulfilled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        verbose_name = 'Permintaan sparepart'
        verbose_name_plural = 'Permintaan sparepart'
        constraints = [models.CheckConstraint(condition=Q(quantity__gt=0), name='inv_request_positive')]
        permissions = [('approve_admin_request', 'Menyetujui permintaan dari admin sparepart')]


class Stocktake(models.Model):
    STATUS = [('draft', 'Sedang dihitung'), ('posted', 'Sudah diposting'), ('cancelled', 'Dibatalkan')]
    title = models.CharField('Nama opname', max_length=120)
    status = models.CharField(max_length=9, choices=STATUS, default='draft', db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name='inventory_stocktakes')
    created_at = models.DateTimeField(auto_now_add=True)
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                  on_delete=models.PROTECT, related_name='inventory_posted_stocktakes')
    posted_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.PROTECT, related_name='inventory_cancelled_stocktakes')
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_note = models.CharField(max_length=600, blank=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        verbose_name = 'Stock opname'
        verbose_name_plural = 'Stock opname'


class StocktakeLine(models.Model):
    stocktake = models.ForeignKey(Stocktake, on_delete=models.PROTECT, related_name='lines')
    part = models.ForeignKey(Part, on_delete=models.PROTECT)
    book_qty = models.DecimalField(max_digits=12, decimal_places=3)
    book_movement_id = models.PositiveBigIntegerField(default=0)
    counted_qty = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True,
                                      validators=[MinValueValidator(ZERO)])
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.PROTECT)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['part__sku']
        constraints = [models.UniqueConstraint(fields=['stocktake', 'part'], name='inv_count_part_unique'),
                       models.CheckConstraint(condition=Q(counted_qty__gte=0) | Q(counted_qty__isnull=True),
                                              name='inv_count_nonnegative')]

    @property
    def difference(self):
        return None if self.counted_qty is None else self.counted_qty - self.book_qty


class StockMovement(models.Model):
    TYPES = [('receive', 'Barang masuk'), ('issue', 'Barang keluar'),
             ('opname', 'Koreksi opname'), ('request', 'Pemenuhan permintaan')]
    part = models.ForeignKey(Part, on_delete=models.PROTECT, related_name='movements')
    kind = models.CharField(max_length=8, choices=TYPES)
    qty_delta = models.DecimalField(max_digits=12, decimal_places=3)
    before_qty = models.DecimalField(max_digits=12, decimal_places=3)
    after_qty = models.DecimalField(max_digits=12, decimal_places=3)
    note = models.CharField(max_length=600, blank=True)
    request = models.ForeignKey(PartRequest, on_delete=models.PROTECT, blank=True, null=True)
    stocktake = models.ForeignKey(Stocktake, on_delete=models.PROTECT, blank=True, null=True)
    import_batch = models.ForeignKey('StockImportBatch', on_delete=models.PROTECT, blank=True, null=True, related_name='movements')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        verbose_name = 'Mutasi stok'
        verbose_name_plural = 'Mutasi stok'
        constraints = [models.CheckConstraint(condition=~Q(qty_delta=0), name='inv_delta_nonzero'),
                       models.CheckConstraint(condition=Q(after_qty__gte=0), name='inv_after_nonnegative')]


class StockImportBatch(models.Model):
    fingerprint = models.CharField('SHA256 isi file', max_length=64, unique=True, editable=False)
    filename = models.CharField('Nama sumber', max_length=200)
    row_count = models.PositiveIntegerField(default=0)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        verbose_name = 'Impor mutasi'
        verbose_name_plural = 'Impor mutasi'
