import csv, io
from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import IntegrityError, transaction
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from .models import Machine, Plan, WorkOrder, AuditEvent
from .services import generate_orders, submit_order, review_order, assign_order, visible_orders
from .importing import FIELDS, import_csv, safe_cell
from .scheduling import due_dates

class PMTests(TestCase):
    def setUp(self):
        User=get_user_model()
        self.admin=User.objects.create_superuser(username='admin',password='test-password-123')
        self.tech=User.objects.create_user(username='tech',password='test-password-456')
        self.other=User.objects.create_user(username='other',password='test-password-789')
        self.m=Machine.objects.create(code='TEST-001',name='Mesin uji')
        self.today=timezone.localdate()
        self.p=Plan.objects.create(machine=self.m,title='Inspeksi SOP uji',interval_days=30,next_due=self.today,checklist='Pemeriksaan A\nPemeriksaan B',assigned_to=self.tech)
    def order(self):
        generate_orders(self.today)
        return WorkOrder.objects.get(plan=self.p,due_date=self.today)
    def csv(self,rows):
        text=io.StringIO(); writer=csv.writer(text); writer.writerow(FIELDS); writer.writerows(rows)
        return text.getvalue().encode('utf-8')
    def test_login_required(self):
        self.assertEqual(self.client.get('/').status_code,302)
    def test_login_page(self):
        self.assertContains(self.client.get('/login/'),'Smart Maintenance')
    def test_health(self):
        self.assertEqual(self.client.get('/healthz').json()['status'],'ok')
    def test_page_templates(self):
        w=self.order(); self.client.force_login(self.admin)
        for path in ['/', '/machines/','/orders/','/machines/import/','/password/',reverse('machine_detail',args=[self.m.uid]),reverse('order_detail',args=[w.pk]),'/admin/']:
            with self.subTest(path=path): self.assertEqual(self.client.get(path).status_code,200)
    def test_scheduler_idempotent(self):
        self.assertEqual(generate_orders(self.today),1)
        self.assertEqual(generate_orders(self.today),0)
        self.assertEqual(WorkOrder.objects.count(),1)
    def test_schedule_fixed_not_completion_based(self):
        self.order(); self.p.refresh_from_db()
        self.assertEqual(self.p.next_due,self.today+timedelta(days=30))
    def test_inactive_machine_skipped(self):
        self.m.active=False; self.m.save(); self.assertEqual(generate_orders(self.today),0)
    def test_inactive_plan_skipped(self):
        self.p.active=False; self.p.save(); self.assertEqual(generate_orders(self.today),0)
    def test_backlog_bounded_not_lost(self):
        start=self.today-timedelta(days=100)
        dates,next_due=due_dates(start,self.today,1)
        self.assertEqual(len(dates),12); self.assertEqual(next_due,start+timedelta(days=12))
    def test_zero_interval_rejected(self):
        with self.assertRaises(ValueError): due_dates(self.today,self.today,0)
    def test_snapshot_stable(self):
        w=self.order(); self.p.checklist='Diubah'; self.p.save()
        w.refresh_from_db(); self.assertEqual(len(w.checklist_snapshot),2)
    def test_unique_workorder_constraint(self):
        w=self.order()
        with self.assertRaises(IntegrityError),transaction.atomic():
            WorkOrder.objects.create(plan=self.p,due_date=w.due_date,title='duplikat')
    def test_submit_requires_assignee(self):
        w=self.order()
        with self.assertRaises(PermissionDenied): submit_order(w.pk,self.other,['ok','ok'],'')
    def test_submit_requires_all_answers(self):
        w=self.order()
        with self.assertRaises(ValidationError): submit_order(w.pk,self.tech,['ok'],'')
    def test_fail_requires_note(self):
        w=self.order()
        with self.assertRaises(ValidationError): submit_order(w.pk,self.tech,['ok','fail'],'')
    def test_submission_review_flow(self):
        w=self.order(); submit_order(w.pk,self.tech,['ok','ok'],'Selesai')
        w.refresh_from_db(); self.assertEqual(w.status,'review')
        review_order(w.pk,self.admin,'approve','Diperiksa')
        w.refresh_from_db(); self.assertEqual(w.status,'done'); self.assertEqual(w.approved_by,self.admin)
    def test_double_submit_rejected(self):
        w=self.order(); submit_order(w.pk,self.tech,['ok','ok'],'')
        with self.assertRaises(ValidationError): submit_order(w.pk,self.tech,['ok','ok'],'')
    def test_self_approval_rejected(self):
        w=self.order(); assign_order(w.pk,self.admin,self.admin); submit_order(w.pk,self.admin,['ok','ok'],'')
        with self.assertRaises(ValidationError): review_order(w.pk,self.admin,'approve','')
    def test_technician_cannot_review(self):
        w=self.order(); submit_order(w.pk,self.tech,['ok','ok'],'')
        with self.assertRaises(PermissionDenied): review_order(w.pk,self.other,'approve','')
    def test_rejection_preserves_audit(self):
        w=self.order(); submit_order(w.pk,self.tech,['ok','fail'],'Perlu diperbaiki')
        review_order(w.pk,self.admin,'reject','Lengkapi pekerjaan')
        w.refresh_from_db(); self.assertEqual(w.status,'open')
        self.assertTrue(w.events.filter(action='submitted').exists())
    def test_reject_requires_reason(self):
        w=self.order(); submit_order(w.pk,self.tech,['ok','ok'],'')
        with self.assertRaises(ValidationError): review_order(w.pk,self.admin,'reject','')
    def test_other_technician_cannot_view_order(self):
        w=self.order(); self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('order_detail',args=[w.pk])).status_code,404)
    def test_csrf_enforced(self):
        w=self.order(); c=Client(enforce_csrf_checks=True); c.force_login(self.tech)
        self.assertEqual(c.post(reverse('order_detail',args=[w.pk]),{'action':'submit'}).status_code,403)
    def test_qr_disabled_until_domain(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('machine_qr',args=[self.m.uid])).status_code,409)
    @override_settings(PUBLIC_BASE_URL='https://pm.example.com')
    def test_qr_svg(self):
        self.client.force_login(self.admin)
        r=self.client.get(reverse('machine_qr',args=[self.m.uid])); self.assertEqual(r.status_code,200)
        self.assertIn(b'<svg',r.content)
    def test_csv_import(self):
        data=self.csv([['NEW-1','Mesin baru','','','','','','']])
        self.assertEqual(import_csv(data,self.admin),1)
    def test_csv_duplicate_is_atomic(self):
        data=self.csv([['NEW-2','Mesin baru','','','','','',''],['TEST-001','Duplikat','','','','','','']])
        with self.assertRaises(ValidationError): import_csv(data,self.admin)
        self.assertFalse(Machine.objects.filter(code='NEW-2').exists())
    def test_csv_invalid_row_is_atomic(self):
        data=self.csv([['NEW-3','Mesin baru','','','','','',''],['','Tidak valid','','','','','','']])
        with self.assertRaises(ValidationError): import_csv(data,self.admin)
        self.assertFalse(Machine.objects.filter(code='NEW-3').exists())
    def test_csv_formula_escape(self):
        self.assertEqual(safe_cell('=1+1'),"'=1+1")
        self.assertEqual(safe_cell('Normal'),'Normal')
    def test_technician_cannot_import(self):
        self.client.force_login(self.tech); self.assertEqual(self.client.get('/machines/import/').status_code,403)
    def test_export(self):
        self.order(); self.client.force_login(self.admin)
        r=self.client.get('/orders/export.csv'); self.assertEqual(r.status_code,200); self.assertIn(b'TEST-001',r.content)
    def test_assignment_audited(self):
        w=self.order(); assign_order(w.pk,self.admin,self.other)
        w.refresh_from_db(); self.assertEqual(w.assigned_to,self.other)
        self.assertTrue(w.events.filter(action='assigned').exists())
    def test_checklist_validation(self):
        self.p.checklist=''
        with self.assertRaises(ValidationError): self.p.full_clean()
