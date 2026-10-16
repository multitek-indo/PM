from importlib import import_module
from pathlib import Path
import tempfile
from django.apps import apps
from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.db import connection, IntegrityError, transaction
from django.test import Client, TestCase, RequestFactory, SimpleTestCase
from django.urls import reverse
from config.version import read_version
from .models import CompanyProfile, DEFAULT_COMPANY_NAME
from .context_processors import company_identity


class CompanyIdentityTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.root = User.objects.create_superuser('identity-root',password='test-only-123456789')
        self.staff = User.objects.create_user('identity-staff',password='test-only-123456789',is_staff=True)
        self.tech = User.objects.create_user('identity-tech',password='test-only-123456789')
        self.group = Group.objects.get(name='Pengelola Identitas Perusahaan')
        self.url = reverse('admin:branding_companyprofile_change',args=[1])

    def login(self,user):
        self.client.force_login(user)

    def test_default_name(self):
        self.assertEqual(CompanyProfile.objects.get(pk=1).company_name,DEFAULT_COMPANY_NAME)

    def test_default_group_only_two_permissions(self):
        self.assertEqual(set(self.group.permissions.values_list('codename',flat=True)),
                         {'view_companyprofile','change_companyprofile'})
        self.assertEqual(self.group.user_set.count(),0)

    def test_old_group_not_auto_granted(self):
        group = Group.objects.create(name='Supervisor PM')
        group.permissions.add(Permission.objects.get(codename='change_machine'))
        self.assertFalse(group.permissions.filter(content_type__app_label='branding').exists())

    def test_superuser_can_edit(self):
        self.login(self.root)
        r=self.client.post(self.url,{'company_name':'PT Contoh Garment','_save':'Simpan'})
        self.assertEqual(r.status_code,302)
        self.assertEqual(CompanyProfile.objects.get().company_name,'PT Contoh Garment')

    def test_edit_is_logged_by_admin(self):
        self.login(self.root)
        self.client.post(self.url,{'company_name':'PT Uji','_save':'Simpan'})
        self.assertTrue(LogEntry.objects.filter(content_type__app_label='branding',user=self.root,action_flag=2).exists())

    def test_no_permission_denied_get(self):
        self.login(self.staff)
        self.assertEqual(self.client.get(self.url).status_code,403)

    def test_no_permission_denied_post(self):
        self.login(self.staff)
        self.assertEqual(self.client.post(self.url,{'company_name':'Tidak Boleh'}).status_code,403)
        self.assertEqual(CompanyProfile.objects.get().company_name,DEFAULT_COMPANY_NAME)

    def test_group_grants_edit(self):
        self.staff.groups.add(self.group); self.login(self.staff)
        self.assertEqual(self.client.post(self.url,{'company_name':'PT Grup','_save':'Simpan'}).status_code,302)
        self.assertEqual(CompanyProfile.objects.get().company_name,'PT Grup')

    def test_view_only_can_read_not_write(self):
        self.staff.user_permissions.add(Permission.objects.get(content_type__app_label='branding',codename='view_companyprofile'))
        self.login(self.staff)
        self.assertEqual(self.client.get(self.url).status_code,200)
        self.assertEqual(self.client.post(self.url,{'company_name':'Tidak Boleh'}).status_code,403)

    def test_nonstaff_with_group_still_cannot_admin(self):
        self.tech.groups.add(self.group); self.login(self.tech)
        self.assertEqual(self.client.get(self.url).status_code,302)
        self.assertEqual(self.client.post(self.url,{'company_name':'Tidak Boleh'}).status_code,302)

    def test_anonymous_cannot_change(self):
        self.assertEqual(self.client.post(self.url,{'company_name':'Tidak Boleh'}).status_code,302)

    def test_csrf_required(self):
        c=Client(enforce_csrf_checks=True); c.force_login(self.root)
        self.assertEqual(c.post(self.url,{'company_name':'CSRF'}).status_code,403)

    def test_add_disabled_even_for_superuser(self):
        self.login(self.root)
        self.assertEqual(self.client.get(reverse('admin:branding_companyprofile_add')).status_code,403)

    def test_delete_disabled_even_for_superuser(self):
        self.login(self.root)
        r=self.client.post(reverse('admin:branding_companyprofile_delete',args=[1]),{'post':'yes'})
        self.assertEqual(r.status_code,403)
        self.assertTrue(CompanyProfile.objects.filter(pk=1).exists())

    def test_empty_name_rejected(self):
        obj=CompanyProfile.objects.get(); obj.company_name='   '
        with self.assertRaises(ValidationError): obj.save()

    def test_long_name_rejected(self):
        obj=CompanyProfile.objects.get(); obj.company_name='a'*121
        with self.assertRaises(ValidationError): obj.save()

    def test_control_character_rejected(self):
        obj=CompanyProfile.objects.get(); obj.company_name='PT\nUji'
        with self.assertRaises(ValidationError): obj.save()

    def test_trims_surrounding_spaces(self):
        obj=CompanyProfile.objects.get(); obj.company_name='  PT Uji  '; obj.save()
        self.assertEqual(CompanyProfile.objects.get().company_name,'PT Uji')

    def test_singleton_validated(self):
        with self.assertRaises(ValidationError): CompanyProfile.objects.create(id=2,company_name='PT Kedua')

    def test_singleton_database_constraint(self):
        with self.assertRaises(IntegrityError),transaction.atomic():
            CompanyProfile.objects.bulk_create([CompanyProfile(id=2,company_name='PT Kedua')])

    def test_login_shows_company(self):
        obj=CompanyProfile.objects.get(); obj.company_name='PT Contoh'; obj.save()
        self.assertContains(self.client.get('/login/'),'PT Contoh')

    def test_company_is_html_escaped(self):
        obj=CompanyProfile.objects.get(); obj.company_name='<script>alert(1)</script>'; obj.save()
        r=self.client.get('/login/')
        self.assertNotContains(r,'<script>alert(1)</script>')
        self.assertContains(r,'&lt;script&gt;')

    def test_dashboard_shows_same_company_and_version(self):
        self.login(self.root)
        r=self.client.get('/')
        self.assertContains(r,DEFAULT_COMPANY_NAME)
        self.assertContains(r,'VERSI '+settings.APP_VERSION)

    def test_admin_shows_company(self):
        self.login(self.root)
        r=self.client.get('/admin/')
        self.assertContains(r,DEFAULT_COMPANY_NAME)
        self.assertContains(r,settings.APP_VERSION)

    def test_changed_name_visible_next_request(self):
        self.client.get('/login/')
        obj=CompanyProfile.objects.get(); obj.company_name='PT Baru'; obj.save()
        self.assertContains(self.client.get('/login/'),'PT Baru')

    def test_read_does_not_recreate_missing_row(self):
        CompanyProfile.objects.all().delete()
        data=company_identity(RequestFactory().get('/login/'))
        self.assertEqual(data['pm_company_name'],DEFAULT_COMPANY_NAME)
        self.assertEqual(CompanyProfile.objects.count(),0)

    def test_group_does_not_grant_maintenance_permission(self):
        self.staff.groups.add(self.group)
        u=get_user_model().objects.get(pk=self.staff.pk)
        self.assertTrue(u.has_perm('branding.change_companyprofile'))
        self.assertFalse(u.has_perm('maintenance.change_machine'))
        self.assertFalse(u.has_perm('auth.change_group'))

    def test_renaming_new_group_keeps_permission(self):
        self.staff.groups.add(self.group)
        self.group.name='Admin Nama Perusahaan'; self.group.save()
        u=get_user_model().objects.get(pk=self.staff.pk)
        self.assertTrue(u.has_perm('branding.change_companyprofile'))

    def test_revoking_group_removes_edit(self):
        self.staff.groups.add(self.group); self.staff.groups.remove(self.group)
        self.login(self.staff)
        self.assertEqual(self.client.post(self.url,{'company_name':'Tidak Boleh'}).status_code,403)

    def test_preexisting_group_conflict_does_not_mutate(self):
        migration=import_module('branding.migrations.0001_initial')
        before=list(self.group.permissions.order_by('pk').values_list('pk',flat=True))
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                class Schema: pass
                schema=Schema(); schema.connection=connection
                migration.seed_identity(apps,schema)
        self.assertEqual(list(self.group.permissions.order_by('pk').values_list('pk',flat=True)),before)


class VersionTests(SimpleTestCase):
    def test_current_version(self):
        self.assertEqual(read_version(),settings.APP_VERSION)

    def test_version_file_rejects_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'version.txt'
            for bad in ['v0.3.0','0.3','01.2.3','1.2.03','1.2.3;id','../version','']:
                p.write_text(bad)
                with self.assertRaises(ValueError): read_version(p)

    def test_valid_semver(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'version.txt'; p.write_text('0.3.12\n')
            self.assertEqual(read_version(p),'0.3.12')
