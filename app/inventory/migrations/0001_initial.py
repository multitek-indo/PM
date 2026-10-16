from decimal import Decimal
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


def make_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.using(schema_editor.connection.alias).get_or_create(name='Pengelola Stok Sparepart')


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL),
                    ('maintenance', '0001_initial')]
    operations = [
        migrations.CreateModel(name='Part', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('sku', models.CharField(max_length=64, unique=True, verbose_name='Kode sparepart')),
            ('name', models.CharField(max_length=160, verbose_name='Nama sparepart')),
            ('machine_type', models.CharField(blank=True, max_length=120, verbose_name='Jenis/tipe mesin')),
            ('unit', models.CharField(choices=[('pcs','Pcs'),('set','Set'),('meter','Meter'),('liter','Liter'),('roll','Roll'),('other','Lainnya')], default='pcs', max_length=8, verbose_name='Satuan')),
            ('location', models.CharField(blank=True, max_length=120, verbose_name='Lokasi penyimpanan')),
            ('current_qty', models.DecimalField(decimal_places=3, default=Decimal('0.000'), max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0.000'))], verbose_name='Stok tersedia')),
            ('min_qty', models.DecimalField(decimal_places=3, default=Decimal('0.000'), max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0.000'))], verbose_name='Batas minimum')),
            ('active', models.BooleanField(default=True, verbose_name='Aktif')),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
        ], options={'ordering':['sku'], 'verbose_name':'Master sparepart', 'verbose_name_plural':'Master sparepart'}),
        migrations.CreateModel(name='Stocktake', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('title', models.CharField(max_length=120, verbose_name='Nama opname')),
            ('status', models.CharField(choices=[('draft','Sedang dihitung'),('posted','Sudah diposting'),('cancelled','Dibatalkan')], db_index=True, default='draft', max_length=9)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('posted_at', models.DateTimeField(blank=True, null=True)),
            ('cancelled_at', models.DateTimeField(blank=True, null=True)),
            ('cancel_note', models.CharField(blank=True, max_length=600)),
            ('cancelled_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='inventory_cancelled_stocktakes', to=settings.AUTH_USER_MODEL)),
            ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='inventory_stocktakes', to=settings.AUTH_USER_MODEL)),
            ('posted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='inventory_posted_stocktakes', to=settings.AUTH_USER_MODEL)),
        ], options={'ordering':['-created_at','-pk'], 'verbose_name':'Stock opname', 'verbose_name_plural':'Stock opname'}),
        migrations.CreateModel(name='PartRequest', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('quantity', models.DecimalField(decimal_places=3, max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0.001'))], verbose_name='Jumlah diminta')),
            ('note', models.CharField(blank=True, max_length=600, verbose_name='Keterangan kebutuhan')),
            ('status', models.CharField(choices=[('pending','Menunggu'),('approved','Disetujui'),('rejected','Ditolak'),('fulfilled','Sudah dikeluarkan')], db_index=True, default='pending', max_length=12)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('decided_at', models.DateTimeField(blank=True, null=True)),
            ('manager_note', models.CharField(blank=True, max_length=600)),
            ('fulfilled_at', models.DateTimeField(blank=True, null=True)),
            ('decided_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='sparepart_decisions', to=settings.AUTH_USER_MODEL)),
            ('fulfilled_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='sparepart_fulfillments', to=settings.AUTH_USER_MODEL)),
            ('order', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='inventory_requests', to='maintenance.workorder')),
            ('part', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='requests', to='inventory.part')),
            ('requested_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='sparepart_requests', to=settings.AUTH_USER_MODEL)),
        ], options={'ordering':['-created_at','-pk'], 'verbose_name':'Permintaan sparepart', 'verbose_name_plural':'Permintaan sparepart'}),
        migrations.CreateModel(name='StocktakeLine', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('book_qty', models.DecimalField(decimal_places=3, max_digits=12)),
            ('book_movement_id', models.PositiveBigIntegerField(default=0)),
            ('counted_qty', models.DecimalField(blank=True, decimal_places=3, max_digits=12, null=True, validators=[django.core.validators.MinValueValidator(Decimal('0.000'))])),
            ('updated_at', models.DateTimeField(blank=True, null=True)),
            ('part', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='inventory.part')),
            ('stocktake', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='lines', to='inventory.stocktake')),
            ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
        ], options={'ordering':['part__sku']}),
        migrations.CreateModel(name='StockMovement', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('kind', models.CharField(choices=[('receive','Barang masuk'),('issue','Barang keluar'),('opname','Koreksi opname'),('request','Pemenuhan permintaan')], max_length=8)),
            ('qty_delta', models.DecimalField(decimal_places=3, max_digits=12)),
            ('before_qty', models.DecimalField(decimal_places=3, max_digits=12)),
            ('after_qty', models.DecimalField(decimal_places=3, max_digits=12)),
            ('note', models.CharField(blank=True, max_length=600)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ('part', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='movements', to='inventory.part')),
            ('request', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='inventory.partrequest')),
            ('stocktake', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='inventory.stocktake')),
        ], options={'ordering':['-created_at','-pk'], 'verbose_name':'Mutasi stok', 'verbose_name_plural':'Mutasi stok'}),
        migrations.AddConstraint(model_name='part', constraint=models.CheckConstraint(condition=models.Q(current_qty__gte=0), name='inv_qty_nonnegative')),
        migrations.AddConstraint(model_name='part', constraint=models.CheckConstraint(condition=models.Q(min_qty__gte=0), name='inv_min_nonnegative')),
        migrations.AddConstraint(model_name='partrequest', constraint=models.CheckConstraint(condition=models.Q(quantity__gt=0), name='inv_request_positive')),
        migrations.AddConstraint(model_name='stocktakeline', constraint=models.UniqueConstraint(fields=('stocktake','part'), name='inv_count_part_unique')),
        migrations.AddConstraint(model_name='stocktakeline', constraint=models.CheckConstraint(condition=models.Q(counted_qty__gte=0)|models.Q(counted_qty__isnull=True), name='inv_count_nonnegative')),
        migrations.AddConstraint(model_name='stockmovement', constraint=models.CheckConstraint(condition=~models.Q(qty_delta=0), name='inv_delta_nonzero')),
        migrations.AddConstraint(model_name='stockmovement', constraint=models.CheckConstraint(condition=models.Q(after_qty__gte=0), name='inv_after_nonnegative')),
        migrations.RunPython(make_group, migrations.RunPython.noop),
    ]
