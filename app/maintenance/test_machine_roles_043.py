"""Permission regression: Django group permissions must work in the PM UI without is_staff."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse
from .models import Machine,Plan

class MachinePermissions043(TestCase):
    def setUp(self):
        U=get_user_model()
        self.machine=Machine.objects.create(code='CUT-043',name='Mesin cutter')
        self.user=U.objects.create_user('sparepart',password='only-testing-12345')
        self.group=Group.objects.create(name='Operator Master Mesin v043')
        self.client.force_login(self.user)

    def allow(self,*codes):
        self.group.permissions.add(*Permission.objects.filter(
            content_type__app_label='maintenance',content_type__model='machine',codename__in=codes))
        self.user.groups.add(self.group)
        self.user=type(self.user).objects.get(pk=self.user.pk)
        self.client.force_login(self.user)

    def test_no_permission_hides_links_and_blocks_posts(self):
        self.assertNotContains(self.client.get(reverse('machines')),'Tambah mesin')
        self.assertEqual(self.client.get(reverse('machine_add')).status_code,403)
        self.assertEqual(self.client.get(reverse('machine_edit',args=[self.machine.uid])).status_code,403)
        self.assertEqual(self.client.post(reverse('machine_delete',args=[self.machine.uid]),{'confirmation':self.machine.code}).status_code,403)
        self.machine.refresh_from_db()

    def test_add_permission_without_staff(self):
        self.allow('add_machine')
        self.assertFalse(self.user.is_staff)
        self.assertContains(self.client.get(reverse('machines')),'Tambah mesin')
        self.assertEqual(self.client.get(reverse('machine_add')).status_code,200)
        self.assertEqual(self.client.get(reverse('machine_edit',args=[self.machine.uid])).status_code,403)
        response=self.client.post(reverse('machine_add'),{'code':'NEW-043','name':'Mesin tambahan','active':'on'})
        self.assertEqual(response.status_code,302)
        self.assertTrue(Machine.objects.filter(code='NEW-043').exists())
        self.assertEqual(self.client.get('/admin/').status_code,302)  # still non-staff

    def test_change_permission_without_staff(self):
        self.allow('change_machine')
        self.assertContains(self.client.get(reverse('machine_detail',args=[self.machine.uid])),'Edit master')
        self.assertEqual(self.client.get(reverse('machine_edit',args=[self.machine.uid])).status_code,200)
        response=self.client.post(reverse('machine_edit',args=[self.machine.uid]),{
            'code':'CUT-043','name':'Mesin diperbaiki','active':'on'})
        self.assertEqual(response.status_code,302)
        self.machine.refresh_from_db();self.assertEqual(self.machine.name,'Mesin diperbaiki')
        self.assertEqual(self.client.get(reverse('machine_add')).status_code,403)

    def test_delete_permission_confirmation_and_protected_history(self):
        self.allow('delete_machine')
        url=reverse('machine_delete',args=[self.machine.uid])
        self.assertEqual(self.client.post(url,{'confirmation':'WRONG'}).status_code,200)
        self.assertTrue(Machine.objects.filter(pk=self.machine.pk).exists())
        plan=Plan.objects.create(machine=self.machine,title='Cek mesin',interval_days=7,
                                 next_due='2026-12-01',checklist='Cek kondisi')
        self.assertEqual(self.client.post(url,{'confirmation':self.machine.code}).status_code,200)
        self.assertTrue(Machine.objects.filter(pk=self.machine.pk).exists())
        plan.delete()
        self.assertEqual(self.client.post(url,{'confirmation':self.machine.code}).status_code,302)
        self.assertFalse(Machine.objects.filter(pk=self.machine.pk).exists())
