from django.db import migrations, models

GROUP_NAME = 'Pengelola Identitas Perusahaan'


def seed_identity(apps, schema_editor):
    alias = schema_editor.connection.alias
    Profile = apps.get_model('branding', 'CompanyProfile')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Permission = apps.get_model('auth', 'Permission')
    Group = apps.get_model('auth', 'Group')
    # Never repurpose an existing group or modify existing user memberships.
    if Group.objects.using(alias).filter(name=GROUP_NAME).exists():
        raise RuntimeError('Grup Pengelola Identitas Perusahaan sudah ada; perlu review, tidak ditimpa.')
    Profile.objects.using(alias).create(id=1, company_name='Multitek Indonesia')
    ct, _ = ContentType.objects.using(alias).get_or_create(app_label='branding', model='companyprofile')
    perms = []
    for codename, name in [('view_companyprofile', 'Dapat melihat nama perusahaan'),
                           ('change_companyprofile', 'Dapat mengubah nama perusahaan')]:
        perm, _ = Permission.objects.using(alias).get_or_create(content_type=ct, codename=codename,
                                                               defaults={'name': name})
        perms.append(perm)
    group = Group.objects.using(alias).create(name=GROUP_NAME)
    group.permissions.add(*perms)


class Migration(migrations.Migration):
    initial = True
    atomic = True
    dependencies = [('auth', '0012_alter_user_first_name_max_length'),
                    ('contenttypes', '0002_remove_content_type_name')]
    operations = [
        migrations.CreateModel(
            name='CompanyProfile',
            fields=[('id', models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False, serialize=False)),
                    ('company_name', models.CharField('Nama perusahaan', max_length=120, default='Multitek Indonesia',
                        help_text='Identitas yang tampil pada aplikasi. Tidak mengubah nama produk, mesin, database, atau domain.')),
                    ('updated_at', models.DateTimeField('Terakhir diperbarui', auto_now=True))],
            options={'verbose_name': 'Identitas perusahaan', 'verbose_name_plural': 'Identitas perusahaan',
                     'default_permissions': (), 'permissions': [
                        ('view_companyprofile', 'Dapat melihat nama perusahaan'),
                        ('change_companyprofile', 'Dapat mengubah nama perusahaan')],
                     'constraints': [models.CheckConstraint(condition=models.Q(id=1), name='pm_company_single_row')]},
        ),
        # Intentionally irreversible: an automatic reverse must not erase identity/permissions.
        migrations.RunPython(seed_identity),
    ]
