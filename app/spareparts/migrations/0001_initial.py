from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ('maintenance', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name='SparepartPhoto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('broken', 'Sparepart rusak'), ('needed', 'Sparepart dibutuhkan')], max_length=8, verbose_name='Keterangan kondisi')),
                ('part_name', models.CharField(max_length=120, validators=[django.core.validators.MinLengthValidator(2)], verbose_name='Nama sparepart')),
                ('note', models.CharField(blank=True, max_length=600, verbose_name='Catatan teknisi')),
                ('filename', models.CharField(editable=False, max_length=36, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='sparepart_photos', to='maintenance.workorder')),
                ('uploaded_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'Foto sparepart', 'verbose_name_plural': 'Foto sparepart', 'ordering': ['-created_at', '-pk']},
        ),
    ]
