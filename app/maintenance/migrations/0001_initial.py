import uuid
import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    initial=True
    dependencies=[migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.CreateModel(name='Machine',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('uid',models.UUIDField(default=uuid.uuid4,editable=False,unique=True)),
            ('code',models.CharField(max_length=64,unique=True,verbose_name='Kode mesin')),
            ('name',models.CharField(max_length=160,verbose_name='Nama mesin')),
            ('category',models.CharField(blank=True,max_length=80,verbose_name='Jenis mesin')),
            ('manufacturer',models.CharField(blank=True,max_length=80,verbose_name='Merek')),
            ('model',models.CharField(blank=True,max_length=100,verbose_name='Model')),
            ('serial',models.CharField(blank=True,max_length=100,verbose_name='Serial number')),
            ('site',models.CharField(blank=True,db_index=True,max_length=100,verbose_name='Pabrik / lokasi')),
            ('line',models.CharField(blank=True,db_index=True,max_length=80,verbose_name='Line produksi')),
            ('active',models.BooleanField(default=True,verbose_name='Aktif dalam pemeliharaan')),
            ('notes',models.TextField(blank=True,verbose_name='Catatan')),
            ('created_at',models.DateTimeField(auto_now_add=True)),
        ],options={'ordering':['code'],'verbose_name':'Mesin','verbose_name_plural':'Mesin'}),
        migrations.CreateModel(name='SchedulerState',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('name',models.CharField(max_length=30,unique=True)),
            ('last_ok',models.DateTimeField(blank=True,null=True)),
            ('generated',models.PositiveIntegerField(default=0)),
        ]),
        migrations.CreateModel(name='Plan',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('title',models.CharField(max_length=160,verbose_name='Nama pekerjaan PM')),
            ('interval_days',models.PositiveIntegerField(help_text='Tentukan dari manual mesin / SOP. Bukan rekomendasi interval otomatis.',validators=[django.core.validators.MinValueValidator(1),django.core.validators.MaxValueValidator(3650)],verbose_name='Interval (hari)')),
            ('next_due',models.DateField(db_index=True,help_text='Scheduler memakai kalender tetap; pekerjaan yang terlambat tidak dihapus.',verbose_name='Jatuh tempo berikut yang belum dibuat')),
            ('checklist',models.TextField(help_text='1-30 baris. Gunakan prosedur aman sesuai manual. Jangan bekerja pada mesin berenergi tanpa prosedur yang sesuai.',verbose_name='Checklist: satu pemeriksaan per baris')),
            ('active',models.BooleanField(default=True,verbose_name='Jadwal aktif')),
            ('machine',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='plans',to='maintenance.machine',verbose_name='Mesin')),
            ('assigned_to',models.ForeignKey(blank=True,limit_choices_to={'is_active':True},null=True,on_delete=django.db.models.deletion.PROTECT,related_name='pm_plans',to=settings.AUTH_USER_MODEL,verbose_name='Teknisi')),
        ],options={'ordering':['next_due','id'],'verbose_name':'Jadwal PM','verbose_name_plural':'Jadwal PM','constraints':[models.CheckConstraint(condition=models.Q(('interval_days__gte',1),('interval_days__lte',3650)),name='pm_valid_interval')]}),
        migrations.CreateModel(name='WorkOrder',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('due_date',models.DateField(db_index=True,verbose_name='Jatuh tempo')),
            ('title',models.CharField(max_length=160)),
            ('checklist_snapshot',models.JSONField(default=list)),
            ('status',models.CharField(choices=[('open','Belum dikerjakan'),('review','Menunggu verifikasi'),('done','Disetujui')],db_index=True,default='open',max_length=12)),
            ('answers',models.JSONField(blank=True,default=list)),
            ('notes',models.TextField(blank=True)),
            ('submitted_at',models.DateTimeField(blank=True,null=True)),
            ('approved_at',models.DateTimeField(blank=True,null=True)),
            ('created_at',models.DateTimeField(auto_now_add=True)),
            ('plan',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='orders',to='maintenance.plan')),
            ('assigned_to',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name='pm_orders',to=settings.AUTH_USER_MODEL)),
            ('submitted_by',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name='pm_submitted',to=settings.AUTH_USER_MODEL)),
            ('approved_by',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name='pm_approved',to=settings.AUTH_USER_MODEL)),
        ],options={'ordering':['due_date','id'],'verbose_name':'Work order','verbose_name_plural':'Work order (riwayat)','constraints':[models.UniqueConstraint(fields=('plan','due_date'),name='pm_unique_plan_due')]}),
        migrations.CreateModel(name='AuditEvent',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('action',models.CharField(max_length=40)),
            ('detail',models.JSONField(default=dict)),
            ('created_at',models.DateTimeField(auto_now_add=True)),
            ('actor',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,to=settings.AUTH_USER_MODEL)),
            ('order',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name='events',to='maintenance.workorder')),
        ],options={'ordering':['-created_at','-id'],'verbose_name':'Riwayat aktivitas','verbose_name_plural':'Riwayat aktivitas'}),
    ]
