import io
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from .models import Machine, AuditEvent
from .importing import import_excel
from .test_tabular import workbook_bytes, row

class Release020Tests(TestCase):
    def setUp(self):
        self.admin=get_user_model().objects.create_superuser('release-admin',password='test-only-password-123')
        self.tech=get_user_model().objects.create_user('release-tech',password='test-only-password-456')
    def file(self,rows=None,name='mesin.xlsx'):
        return SimpleUploadedFile(name,workbook_bytes(rows if rows is not None else [row()]),content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    def test_import_excel(self):
        self.assertEqual(import_excel(workbook_bytes([row()]),self.admin),1)
        self.assertEqual(Machine.objects.get().serial,'000123')
    def test_import_excel_audit(self):
        import_excel(workbook_bytes([row()]),self.admin)
        self.assertEqual(AuditEvent.objects.get().detail['format'],'xlsx')
    def test_duplicate_database_is_atomic(self):
        Machine.objects.create(code='DUP',name='Lama')
        with self.assertRaises(ValidationError): import_excel(workbook_bytes([row('NEW'),row('DUP')]),self.admin)
        self.assertEqual(Machine.objects.count(),1); self.assertEqual(Machine.objects.get().name,'Lama')
    def test_duplicate_file_is_atomic(self):
        with self.assertRaises(ValidationError): import_excel(workbook_bytes([row('DUP'),row('DUP')]),self.admin)
        self.assertEqual(Machine.objects.count(),0)
    def test_invalid_name_is_atomic(self):
        with self.assertRaises(ValidationError): import_excel(workbook_bytes([row('NEW'),row('INVALID','')]),self.admin)
        self.assertEqual(Machine.objects.count(),0)
    def test_long_code_is_atomic(self):
        with self.assertRaises(ValidationError): import_excel(workbook_bytes([row('A'*65)]),self.admin)
        self.assertEqual(Machine.objects.count(),0)
    def test_post_excel(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post('/machines/import/',{'file':self.file()}).status_code,302)
        self.assertEqual(Machine.objects.count(),1)
    def test_tech_cannot_import_excel(self):
        self.client.force_login(self.tech)
        self.assertEqual(self.client.post('/machines/import/',{'file':self.file()}).status_code,403)
        self.assertFalse(Machine.objects.exists())
    def test_import_keeps_csrf(self):
        c=Client(enforce_csrf_checks=True); c.force_login(self.admin)
        self.assertEqual(c.post('/machines/import/',{'file':self.file()}).status_code,403)
    def test_xls_has_clear_error(self):
        self.client.force_login(self.admin)
        r=self.client.post('/machines/import/',{'file':self.file(name='mesin.xls')})
        self.assertContains(r,'Save As'); self.assertFalse(Machine.objects.exists())
    def test_download_xlsx(self):
        self.client.force_login(self.admin); r=self.client.get('/machines/template.xlsx')
        self.assertEqual(r.status_code,200); self.assertTrue(r.content.startswith(b'PK'))
    def test_template_permission(self):
        self.client.force_login(self.tech); self.assertEqual(self.client.get('/machines/template.xlsx').status_code,403)
    def test_clock_authentication(self):
        self.assertEqual(self.client.get('/api/time/').status_code,302)
    def test_clock(self):
        self.client.force_login(self.tech); r=self.client.get('/api/time/')
        self.assertEqual(r.status_code,200); self.assertEqual(r.json()['timezone'],'Asia/Jakarta')
        self.assertLess(abs(r.json()['epoch_ms']/1000-timezone.now().timestamp()),10)
        self.assertIn('no-store',r['Cache-Control'])
    def test_clock_get_only(self):
        self.client.force_login(self.admin); self.assertEqual(self.client.post('/api/time/').status_code,405)
    def test_dashboard_has_clock(self):
        self.client.force_login(self.admin); r=self.client.get('/')
        self.assertContains(r,'data-pm-clock'); self.assertContains(r,'WIB / UTC+7'); self.assertContains(r,'?v=020')
    def test_admin_landing(self):
        self.client.force_login(self.admin); r=self.client.get('/admin/')
        self.assertContains(r,'Administrasi lebih terarah.'); self.assertContains(r,'pm-admin.css')
    def test_admin_machine_form(self):
        self.client.force_login(self.admin); r=self.client.get('/admin/maintenance/machine/add/')
        self.assertContains(r,'Identitas mesin'); self.assertContains(r,'Lokasi &amp; pemeliharaan')
    def test_admin_plan_form(self):
        self.client.force_login(self.admin); r=self.client.get('/admin/maintenance/plan/add/')
        self.assertContains(r,'Waktu &amp; penugasan'); self.assertContains(r,'Checklist pemeriksaan')
    def test_admin_permissions_still_apply(self):
        limited=get_user_model().objects.create_user('limited',is_staff=True)
        limited.user_permissions.add(Permission.objects.get(codename='view_machine',content_type__app_label='maintenance'))
        self.client.force_login(limited); r=self.client.get('/admin/')
        self.assertContains(r,'/admin/maintenance/machine/')
        self.assertNotContains(r,'/admin/auth/user/'); self.assertNotContains(r,'/admin/maintenance/machine/add/')
    def test_history_not_editable(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get('/admin/maintenance/workorder/add/').status_code,403)
    def test_health_version(self):
        from django.conf import settings
        self.assertEqual(self.client.get('/healthz').json()['version'],settings.APP_VERSION)
