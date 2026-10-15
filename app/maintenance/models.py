import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone

class Machine(models.Model):
    uid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    code = models.CharField('Kode mesin', max_length=64, unique=True)
    name = models.CharField('Nama mesin', max_length=160)
    category = models.CharField('Jenis mesin', max_length=80, blank=True)
    manufacturer = models.CharField('Merek', max_length=80, blank=True)
    model = models.CharField('Model', max_length=100, blank=True)
    serial = models.CharField('Serial number', max_length=100, blank=True)
    site = models.CharField('Pabrik / lokasi', max_length=100, blank=True, db_index=True)
    line = models.CharField('Line produksi', max_length=80, blank=True, db_index=True)
    active = models.BooleanField('Aktif dalam pemeliharaan', default=True)
    notes = models.TextField('Catatan', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['code']
        verbose_name = 'Mesin'
        verbose_name_plural = 'Mesin'
    def __str__(self): return f'{self.code} - {self.name}'
    def clean(self):
        self.code = self.code.strip()
        self.name = self.name.strip()
        if not self.code or not self.name:
            raise ValidationError('Kode dan nama mesin wajib diisi.')

class Plan(models.Model):
    machine = models.ForeignKey(Machine, on_delete=models.PROTECT, related_name='plans', verbose_name='Mesin')
    title = models.CharField('Nama pekerjaan PM', max_length=160)
    interval_days = models.PositiveIntegerField('Interval (hari)', validators=[MinValueValidator(1),MaxValueValidator(3650)], help_text='Tentukan dari manual mesin / SOP. Bukan rekomendasi interval otomatis.')
    next_due = models.DateField('Jatuh tempo berikut yang belum dibuat', db_index=True, help_text='Scheduler memakai kalender tetap; pekerjaan yang terlambat tidak dihapus.')
    checklist = models.TextField('Checklist: satu pemeriksaan per baris', help_text='1-30 baris. Gunakan prosedur aman sesuai manual. Jangan bekerja pada mesin berenergi tanpa prosedur yang sesuai.')
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='pm_plans', verbose_name='Teknisi', limit_choices_to={'is_active':True})
    active = models.BooleanField('Jadwal aktif', default=True)
    class Meta:
        ordering = ['next_due', 'id']
        verbose_name = 'Jadwal PM'
        verbose_name_plural = 'Jadwal PM'
        constraints = [models.CheckConstraint(condition=models.Q(interval_days__gte=1,interval_days__lte=3650),name='pm_valid_interval')]
    def __str__(self): return f'{self.machine.code} - {self.title}'
    def clean(self):
        lines = [s.strip() for s in self.checklist.splitlines() if s.strip()]
        if not 1 <= len(lines) <= 30 or any(len(s)>240 for s in lines):
            raise ValidationError({'checklist':'Isi 1-30 baris, maksimal 240 karakter per baris.'})
        self.checklist = '\n'.join(lines)
        if self.next_due and self.next_due.year > 2090:
            raise ValidationError({'next_due':'Tanggal maksimal tahun 2090 untuk pilot ini.'})

class WorkOrder(models.Model):
    STATUS = [('open','Belum dikerjakan'),('review','Menunggu verifikasi'),('done','Disetujui')]
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='orders')
    due_date = models.DateField('Jatuh tempo', db_index=True)
    title = models.CharField(max_length=160)
    checklist_snapshot = models.JSONField(default=list)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='pm_orders')
    status = models.CharField(max_length=12, choices=STATUS, default='open', db_index=True)
    answers = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='pm_submitted')
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='pm_approved')
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['due_date','id']
        verbose_name = 'Work order'
        verbose_name_plural = 'Work order (riwayat)'
        constraints = [models.UniqueConstraint(fields=['plan','due_date'],name='pm_unique_plan_due')]
    @property
    def overdue(self): return self.status != 'done' and self.due_date < timezone.localdate()
    def __str__(self): return f'WO-{self.pk:06d}' if self.pk else 'Work order baru'

class AuditEvent(models.Model):
    order = models.ForeignKey(WorkOrder, on_delete=models.PROTECT, null=True, blank=True, related_name='events')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    action = models.CharField(max_length=40)
    detail = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-created_at','-id']
        verbose_name = 'Riwayat aktivitas'
        verbose_name_plural = 'Riwayat aktivitas'

class SchedulerState(models.Model):
    name = models.CharField(max_length=30, unique=True)
    last_ok = models.DateTimeField(null=True, blank=True)
    generated = models.PositiveIntegerField(default=0)
