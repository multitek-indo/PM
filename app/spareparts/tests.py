import io
import tempfile
from datetime import date
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings, Client
from django.urls import reverse
from PIL import Image
from maintenance.models import Machine, Plan, WorkOrder
from .models import SparepartPhoto


def photo_file(fmt='JPEG', exif=False):
    im = Image.new('RGB', (100, 70), '#208cc3')
    kw = {}
    if exif:
        ex = Image.Exif()
        ex[0x010E] = 'private camera information'
        kw['exif'] = ex
    buf = io.BytesIO()
    im.save(buf, format=fmt, **kw)
    return SimpleUploadedFile('sparepart.' + ('jpg' if fmt == 'JPEG' else fmt.lower()),
                              buf.getvalue(), content_type='image/jpeg' if fmt == 'JPEG' else 'image/png')


class SparepartTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.folder = tempfile.TemporaryDirectory(prefix='pm-photos-test-')
        cls.storage_settings = override_settings(PM_SPAREPART_STORAGE_DIR=cls.folder.name)
        cls.storage_settings.enable()

    @classmethod
    def tearDownClass(cls):
        cls.storage_settings.disable()
        cls.folder.cleanup()
        super().tearDownClass()

    def setUp(self):
        U = get_user_model()
        self.tech = U.objects.create_user('photo-tech', password='safe-password-001')
        self.other = U.objects.create_user('photo-other', password='safe-password-002')
        self.manager = U.objects.create_user('photo-manager', password='safe-password-003')
        self.admin = U.objects.create_superuser('photo-admin', password='safe-password-004', email='admin@example.test')
        group, _ = Group.objects.get_or_create(name='Supervisor PM')
        self.manager.groups.add(group)
        self.machine = Machine.objects.create(code='TEST-FOTO-001', name='Mesin uji')
        self.plan = Plan.objects.create(machine=self.machine, title='PM', interval_days=30,
                                        next_due=date(2026, 11, 1), checklist='Inspeksi bearing', assigned_to=self.tech)
        self.order = WorkOrder.objects.create(plan=self.plan, title='PM', due_date=date(2026, 11, 1),
                                               checklist_snapshot=['Inspeksi bearing'], assigned_to=self.tech)

    def upload(self, user=None, img=None, name='Bearing mesin'):
        self.client.force_login(user or self.tech)
        return self.client.post(reverse('sparepart_upload_photo', args=[self.order.pk]), {
            'kind': 'broken', 'part_name': name, 'note': 'Berisik', 'photo': img or photo_file(),
        })

    def test_upload_does_not_change_workorder_state(self):
        self.assertEqual(self.upload().status_code, 302)
        item = SparepartPhoto.objects.get()
        self.assertEqual(item.order, self.order)
        self.assertEqual(item.uploaded_by, self.tech)
        self.assertTrue(Path(self.folder.name, item.filename).is_file())
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'open')
        self.assertEqual(self.order.answers, [])

    def test_manager_admin_and_assigned_technician_can_view(self):
        self.upload()
        item = SparepartPhoto.objects.get()
        for u in (self.tech, self.manager, self.admin):
            self.client.force_login(u)
            res = self.client.get(reverse('sparepart_view_photo', args=[item.pk]))
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res['Content-Type'], 'image/jpeg')
            self.assertEqual(res['Cache-Control'], 'private, no-store, max-age=0')
            res.close()

    def test_unassigned_technician_cannot_view(self):
        self.upload()
        item = SparepartPhoto.objects.get()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('sparepart_view_photo', args=[item.pk])).status_code, 404)

    def test_unauthenticated_photo_requires_login(self):
        self.upload()
        self.client.logout()
        item = SparepartPhoto.objects.get()
        self.assertEqual(self.client.get(reverse('sparepart_view_photo', args=[item.pk])).status_code, 302)

    def test_other_tech_and_manager_cannot_upload(self):
        self.assertEqual(self.upload(self.other).status_code, 404)
        self.assertEqual(self.upload(self.manager).status_code, 403)
        self.assertFalse(SparepartPhoto.objects.exists())

    def test_status_review_blocks_upload(self):
        self.order.status = 'review'
        self.order.save(update_fields=['status'])
        self.assertEqual(self.upload().status_code, 403)

    def test_fake_image_is_rejected(self):
        bad = SimpleUploadedFile('evil.jpg', b'<html>not image</html>', content_type='image/jpeg')
        self.assertEqual(self.upload(img=bad).status_code, 302)
        self.assertFalse(SparepartPhoto.objects.exists())

    def test_png_and_exif_become_plain_jpeg(self):
        self.upload(img=photo_file('PNG'))
        self.upload(img=photo_file(exif=True))
        for item in SparepartPhoto.objects.all():
            with Image.open(Path(self.folder.name, item.filename)) as im:
                self.assertEqual(im.format, 'JPEG')
                self.assertEqual(dict(im.getexif()), {})

    def test_oversize_is_rejected(self):
        too_big = SimpleUploadedFile('huge.jpg', b'a' * (6*1024*1024+1), content_type='image/jpeg')
        self.assertEqual(self.upload(img=too_big).status_code, 302)
        self.assertFalse(SparepartPhoto.objects.exists())

    def test_max_ten_per_order(self):
        for i in range(11):
            self.assertEqual(self.upload().status_code, 302)
        self.assertEqual(SparepartPhoto.objects.count(), 10)

    def test_required_part_name(self):
        self.upload(name='')
        self.assertFalse(SparepartPhoto.objects.exists())

    def test_csrf_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.tech)
        response = client.post(reverse('sparepart_upload_photo', args=[self.order.pk]),
                               {'kind':'broken','part_name':'Bearing','photo':photo_file()})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(SparepartPhoto.objects.exists())

    def test_photo_shown_on_existing_order_page(self):
        self.upload(name='Servo drive')
        response = self.client.get(reverse('order_detail', args=[self.order.pk]))
        self.assertContains(response, 'Servo drive')
        self.assertContains(response, 'Foto sparepart')

    def test_upload_get_not_allowed(self):
        self.client.force_login(self.tech)
        self.assertEqual(self.client.get(reverse('sparepart_upload_photo', args=[self.order.pk])).status_code, 405)
