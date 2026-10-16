from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


def grant_manager_permission(apps, schema_editor):
    Group = apps.get_model('auth','Group')
    Permission = apps.get_model('auth','Permission')
    ContentType = apps.get_model('contenttypes','ContentType')
    PartRequest = apps.get_model('inventory','PartRequest')
    User = apps.get_model(*settings.AUTH_USER_MODEL.split('.'))
    ct, _ = ContentType.objects.using(schema_editor.connection.alias).get_or_create(app_label='inventory', model='partrequest')
    permission, _ = Permission.objects.using(schema_editor.connection.alias).get_or_create(
        content_type=ct, codename='approve_admin_request',
        defaults={'name':'Menyetujui permintaan dari admin sparepart'})
    manager, _ = Group.objects.using(schema_editor.connection.alias).get_or_create(name='Manager Sparepart')
    manager.permissions.add(permission)
    requester_ids = set(User.objects.using(schema_editor.connection.alias).filter(
        models.Q(groups__name='Pengelola Stok Sparepart') |
        models.Q(groups__name='Supervisor PM') |
        models.Q(is_superuser=True)).values_list('pk',flat=True))
    PartRequest.objects.using(schema_editor.connection.alias).filter(status='pending',requested_by_id__in=requester_ids).update(approval_route='manager')


class Migration(migrations.Migration):
    dependencies = [('inventory','0001_initial'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(
            model_name='partrequest',name='approval_route',
            field=models.CharField(choices=[('stock_admin','Admin sparepart'),('manager','Manager sparepart')],
                                   default='stock_admin',max_length=12,verbose_name='Jalur persetujuan')),
        migrations.CreateModel(name='StockImportBatch',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('fingerprint',models.CharField(editable=False,max_length=64,unique=True,verbose_name='SHA256 isi file')),
            ('filename',models.CharField(max_length=200,verbose_name='Nama sumber')),
            ('row_count',models.PositiveIntegerField(default=0)),
            ('created_at',models.DateTimeField(auto_now_add=True)),
            ('actor',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to=settings.AUTH_USER_MODEL)),
        ],options={'verbose_name':'Impor mutasi','verbose_name_plural':'Impor mutasi','ordering':['-created_at','-pk']}),
        migrations.AddField(model_name='stockmovement',name='import_batch',
            field=models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name='movements',to='inventory.stockimportbatch')),
        migrations.AlterModelOptions(name='partrequest',options={
            'ordering':['-created_at','-pk'], 'verbose_name':'Permintaan sparepart',
            'verbose_name_plural':'Permintaan sparepart','permissions':[('approve_admin_request','Menyetujui permintaan dari admin sparepart')]}),
        migrations.RunPython(grant_manager_permission,migrations.RunPython.noop),
    ]
