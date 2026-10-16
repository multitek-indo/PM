"""Inventory 0.4.4: explicit workflow, idempotent events and separated approvals."""
from django.db import migrations, models
import django.db.models.deletion
import django.core.validators
import decimal
import hashlib
import json
from django.conf import settings


def backfill_and_grant(apps, schema_editor):
    db = schema_editor.connection.alias
    Group=apps.get_model('auth','Group')
    Permission=apps.get_model('auth','Permission')
    ContentType=apps.get_model('contenttypes','ContentType')
    PartRequest=apps.get_model('inventory','PartRequest')
    StockImportBatch=apps.get_model('inventory','StockImportBatch')
    # Snapshot old routes; never create retroactive positive or negative movements.
    PartRequest.objects.using(db).filter(approval_route='manager').update(request_type='replenishment')
    # Existing fulfilled technician requests were already physically handed over.
    # Restore documentary issued_qty ONLY when a matching historic movement exists.
    from django.db.models import F
    from_inventory = apps.get_model('inventory','StockMovement')
    prior_ids=from_inventory.objects.using(db).filter(request_id__isnull=False,qty_delta__lt=0).values_list('request_id',flat=True).distinct()
    PartRequest.objects.using(db).filter(status='fulfilled',approval_route='stock_admin',pk__in=prior_ids).update(issued_qty=F('quantity'))
    StockImportBatch.objects.using(db).all().update(status='posted')
    # Fingerprint-only legacy imports are rebuilt into semantic signatures from
    # their ACTUAL posted movements (no stock is changed). They block repeat
    # uploads in another CSV newline format or XLSX serialization.
    taken={}
    movements=apps.get_model('inventory','StockMovement')
    for batch in StockImportBatch.objects.using(db).order_by('pk').iterator(chunk_size=150):
        rows=[]
        for row in movements.objects.using(db).filter(import_batch_id=batch.pk).values('part__sku','kind','qty_delta','note').iterator(chunk_size=500):
            qty=row['qty_delta']
            if qty is None or qty != qty.to_integral_value():
                continue
            rows.append({'sku':row['part__sku'],'kind':row['kind'],
                         'qty':str(int(abs(qty))),'note':(row['note'] or '').strip()})
        keys={(r['kind']) for r in rows}
        if rows and len(keys)==1 and keys.issubset({'receive','issue'}):
            signature=hashlib.sha256(json.dumps(sorted(rows,key=lambda x:(x['sku'],x['kind'],x['qty'],x['note'])),
                ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            if signature in taken:
                # Do not collapse or rewrite historical duplicates. Preflight
                # normally catches these; keep the record for explicit audit.
                batch.document_id='LEGACY-'+str(batch.pk)
                batch.save(update_fields=['document_id'])
                continue
            taken[signature]=batch.pk
            batch.semantic_hash=signature
            batch.document_id='LEGACY-'+str(batch.pk)
            batch.save(update_fields=['semantic_hash','document_id'])
        else:
            batch.document_id='LEGACY-'+str(batch.pk)
            batch.save(update_fields=['document_id'])
    manager,_=Group.objects.using(db).get_or_create(name='Manager Sparepart')
    catalog,_=Group.objects.using(db).get_or_create(name='Pengelola Stok Sparepart')
    manager_perms=[('inventory','inventoryaudit','view_all_inventory'),
        ('inventory','stocktake','approve_stocktake'),
        ('inventory','manualstockrequest','approve_manual_stock'),
        ('inventory','stockimportbatch','approve_stock_import'),
        ('maintenance','workorder','view_workorder'),
        ('maintenance','machine','view_machine'),
        ('inventory','stockmovement','view_stockmovement'),
        ('inventory','stocktake','view_stocktake')]
    for app,model,code in manager_perms:
        ct,_=ContentType.objects.using(db).get_or_create(app_label=app,model=model)
        perm,_=Permission.objects.using(db).get_or_create(content_type=ct,codename=code,defaults={'name':'Pemantauan '+code})
        manager.permissions.add(perm)
    for code in ('view_machine','add_machine','change_machine'):
        ct,_=ContentType.objects.using(db).get_or_create(app_label='maintenance',model='machine')
        perm,_=Permission.objects.using(db).get_or_create(content_type=ct,codename=code,defaults={'name':'Izin '+code})
        catalog.permissions.add(perm)


class Migration(migrations.Migration):
    dependencies=[('inventory','0002_v043_import_and_approval'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.AddField(model_name='partrequest',name='procurement_ref',field=models.CharField(max_length=90,blank=True,verbose_name='Nomor pengajuan pengadaan')),
        migrations.AddField(model_name='partrequest',name='supplier',field=models.CharField(max_length=160,blank=True,verbose_name='Pemasok (jika diketahui)')),
        migrations.AddField(model_name='partrequest',name='estimated_unit_price',field=models.DecimalField(max_digits=15,decimal_places=2,null=True,blank=True,verbose_name='Estimasi harga per satuan (Rp)',validators=[django.core.validators.MinValueValidator(decimal.Decimal('0'))])),
        migrations.AddField(model_name='partrequest',name='needed_by',field=models.DateField(null=True,blank=True,verbose_name='Tanggal kebutuhan')),
        migrations.AddField(model_name='partrequest',name='request_type',field=models.CharField(max_length=16,choices=[('consumption','Pemakaian teknisi'),('replenishment','Penambahan stok')],default='consumption',verbose_name='Jenis kebutuhan')),
        migrations.AddField(model_name='partrequest',name='ledger_phase',field=models.CharField(max_length=12,choices=[('legacy','Riwayat lama'),('debited','Dikurangi'),('credited','Ditambahkan'),('reversed','Dikembalikan')],default='legacy',verbose_name='Posisi posting stok')),
        migrations.AddField(model_name='partrequest',name='issued_qty',field=models.DecimalField(max_digits=12,decimal_places=3,default=decimal.Decimal('0.000'))),
        migrations.AddField(model_name='partrequest',name='returned_qty',field=models.DecimalField(max_digits=12,decimal_places=3,default=decimal.Decimal('0.000'))),
        migrations.AddField(model_name='partrequest',name='cancelled_at',field=models.DateTimeField(null=True,blank=True)),
        migrations.AddField(model_name='partrequest',name='cancel_note',field=models.CharField(max_length=600,blank=True)),
        migrations.AddField(model_name='partrequest',name='cancelled_by',field=models.ForeignKey(to=settings.AUTH_USER_MODEL,on_delete=django.db.models.deletion.PROTECT,null=True,blank=True,related_name='inventory_request_cancellations')),
        migrations.AlterField(model_name='partrequest',name='status',field=models.CharField(max_length=12,choices=[('pending','Menunggu'),('approved','Disetujui'),('rejected','Ditolak'),('fulfilled','Selesai'),('partial','Diserahkan sebagian'),('cancelled','Dibatalkan')],db_index=True,default='pending')),
        migrations.AddField(model_name='stockmovement',name='event_key',field=models.CharField(max_length=100,blank=True,null=True,unique=True,editable=False)),
        migrations.AddConstraint(model_name='stockmovement',constraint=models.CheckConstraint(condition=models.Q(before_qty__gte=0),name='inv_before_nonnegative')),
        migrations.AddConstraint(model_name='stockmovement',constraint=models.CheckConstraint(condition=models.Q(after_qty=models.F('before_qty')+models.F('qty_delta')),name='inv_movement_arithmetic')),
        migrations.AddField(model_name='stockimportbatch',name='document_id',field=models.CharField(max_length=90,blank=True,null=True,unique=True,verbose_name='Nomor dokumen')),
        migrations.AddField(model_name='stockimportbatch',name='semantic_hash',field=models.CharField(max_length=64,blank=True,null=True,unique=True,verbose_name='Checksum transaksi normal')),
        migrations.AddField(model_name='stockimportbatch',name='kind',field=models.CharField(max_length=8,choices=[('receive','Barang masuk'),('issue','Barang keluar')],default='receive')),
        migrations.AddField(model_name='stockimportbatch',name='status',field=models.CharField(max_length=10,choices=[('pending','Menunggu manager'),('posted','Sudah diposting'),('rejected','Ditolak')],default='pending')),
        migrations.AddField(model_name='stockimportbatch',name='decided_by',field=models.ForeignKey(to=settings.AUTH_USER_MODEL,on_delete=django.db.models.deletion.PROTECT,null=True,blank=True,related_name='inventory_import_decisions')),
        migrations.AddField(model_name='stockimportbatch',name='decided_at',field=models.DateTimeField(null=True,blank=True)),
        migrations.AddField(model_name='stockimportbatch',name='decision_note',field=models.CharField(max_length=600,blank=True)),
        migrations.AlterModelOptions(name='stockimportbatch',options={'ordering':['-created_at','-pk'],'verbose_name':'Impor mutasi','verbose_name_plural':'Impor mutasi','permissions':[('approve_stock_import','Menyetujui impor mutasi sparepart')]}),
        migrations.AlterModelOptions(name='stocktake',options={'ordering':['-created_at','-pk'],'verbose_name':'Stock opname','verbose_name_plural':'Stock opname','permissions':[('approve_stocktake','Memposting koreksi stok opname terpisah')]}),
        migrations.CreateModel(name='ManualStockRequest',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('kind',models.CharField(max_length=8,choices=[('receive','Barang masuk'),('issue','Barang keluar')])),
            ('quantity',models.DecimalField(max_digits=12,decimal_places=3)),
            ('document_no',models.CharField(max_length=90,unique=True)),
            ('note',models.CharField(max_length=600)),
            ('status',models.CharField(max_length=10,choices=[('pending','Menunggu manager'),('posted','Sudah diposting'),('rejected','Ditolak')],default='pending')),
            ('decided_at',models.DateTimeField(null=True,blank=True)),
            ('decision_note',models.CharField(max_length=600,blank=True)),
            ('created_at',models.DateTimeField(auto_now_add=True)),
            ('part',models.ForeignKey(to='inventory.part',on_delete=django.db.models.deletion.PROTECT)),
            ('requested_by',models.ForeignKey(to=settings.AUTH_USER_MODEL,on_delete=django.db.models.deletion.PROTECT,related_name='manual_stock_requests')),
            ('decided_by',models.ForeignKey(to=settings.AUTH_USER_MODEL,on_delete=django.db.models.deletion.PROTECT,null=True,blank=True,related_name='manual_stock_decisions')),
        ],options={'ordering':['-created_at','-pk'],'permissions':[('approve_manual_stock','Menyetujui mutasi manual oleh petugas')],
                   'constraints':[models.CheckConstraint(condition=models.Q(quantity__gt=0),name='inv_manual_qty_positive')]}),
        migrations.CreateModel(name='StockImportLine',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('line_no',models.PositiveIntegerField()),
            ('kind',models.CharField(max_length=8,choices=[('receive','Barang masuk'),('issue','Barang keluar')])),
            ('quantity',models.DecimalField(max_digits=12,decimal_places=3)),
            ('reference',models.CharField(max_length=600)),
            ('batch',models.ForeignKey(to='inventory.stockimportbatch',on_delete=django.db.models.deletion.PROTECT,related_name='lines')),
            ('part',models.ForeignKey(to='inventory.part',on_delete=django.db.models.deletion.PROTECT)),
        ],options={'constraints':[models.UniqueConstraint(fields=['batch','line_no'],name='inv_import_line_unique'),models.CheckConstraint(condition=models.Q(quantity__gt=0),name='inv_import_line_positive')]}),
        migrations.CreateModel(name='InventoryAudit',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('entity_type',models.CharField(max_length=32)),
            ('entity_pk',models.CharField(max_length=64)),
            ('action',models.CharField(max_length=40)),
            ('before',models.JSONField(default=dict)),
            ('after',models.JSONField(default=dict)),
            ('reason',models.CharField(max_length=600,blank=True)),
            ('created_at',models.DateTimeField(auto_now_add=True)),
            ('actor',models.ForeignKey(to=settings.AUTH_USER_MODEL,on_delete=django.db.models.deletion.PROTECT)),
        ],options={'ordering':['-created_at','-pk'],'permissions':[('view_all_inventory','Memantau seluruh aktivitas inventaris')]}),
        migrations.RunPython(backfill_and_grant,migrations.RunPython.noop),
    ]
