"""Run together with maintenance, branding, spareparts on isolated SQLite."""
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse
from maintenance.models import Machine, Plan, WorkOrder
from .models import Part, PartRequest, StockMovement, Stocktake, StocktakeLine
from .services import (can_manage, move_stock, make_request, review_request,
                       fulfill_request, start_stocktake, count_line, post_stocktake, cancel_stocktake)
from .forms import RequestForm

D = Decimal


class InventoryTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.manager = User.objects.create_superuser('stock-admin',password='isolated-test-pass-12345')
        self.tech = User.objects.create_user('stock-tech',password='isolated-test-pass-12345')
        self.other = User.objects.create_user('stock-other',password='isolated-test-pass-12345')
        self.part = Part.objects.create(sku='BEARING-01',name='Bearing jarum',unit='pcs',min_qty=D('2.000'))
        self.machine = Machine.objects.create(code='INV-M1',name='Mesin inventaris')
        self.plan = Plan.objects.create(machine=self.machine,title='Cek bearing',interval_days=30,
                                        next_due='2026-11-01',checklist='Pemeriksaan awal',assigned_to=self.tech)
        self.wo = WorkOrder.objects.create(plan=self.plan,due_date='2026-11-01',
                                            title='Periksa bearing',checklist_snapshot=['Pemeriksaan awal'],assigned_to=self.tech)

    def test_empty_stock_and_minimum(self):
        self.assertEqual(self.part.current_qty,D('0'))
        self.client.force_login(self.tech)
        self.assertContains(self.client.get('/inventory/'),'BEARING-01')
        self.assertContains(self.client.get('/inventory/'),'Perlu stok')

    def test_requires_login(self):
        for path in ['/inventory/','/inventory/requests/','/inventory/opname/']:
            self.assertEqual(self.client.get(path).status_code,302)

    def test_technician_sees_stock_but_not_actions(self):
        self.client.force_login(self.tech)
        self.assertContains(self.client.get('/inventory/'),'Ajukan kebutuhan')
        self.assertNotContains(self.client.get('/inventory/'),'Mulai opname fisik')
        self.assertEqual(self.client.get('/inventory/movement/').status_code,403)
        self.assertEqual(self.client.get('/inventory/parts/new/').status_code,403)
        self.assertEqual(self.client.get('/inventory/opname/').status_code,403)

    def test_manager_and_group_access(self):
        self.assertTrue(can_manage(self.manager))
        self.assertFalse(can_manage(self.tech))
        group=Group.objects.get(name='Pengelola Stok Sparepart')
        self.tech.groups.add(group)
        self.assertTrue(can_manage(self.tech))
        self.client.force_login(self.tech)
        self.assertEqual(self.client.get('/inventory/movement/').status_code,200)

    def test_receive_and_issue_create_ledger(self):
        move_stock(self.part.pk,'receive',D('7'),self.manager,'GRN #100')
        move_stock(self.part.pk,'issue',D('2'),self.manager,'Pemakaian manual')
        self.part.refresh_from_db()
        self.assertEqual(self.part.current_qty,D('5'))
        self.assertEqual(StockMovement.objects.count(),2)
        self.assertEqual(StockMovement.objects.order_by('pk').last().after_qty,D('5'))

    def test_refuse_negative_stock_without_audit(self):
        with self.assertRaises(ValidationError):
            move_stock(self.part.pk,'issue',D('1'),self.manager,'Tidak ada barang')
        self.part.refresh_from_db()
        self.assertEqual(self.part.current_qty,D('0'))
        self.assertFalse(StockMovement.objects.exists())

    def test_technician_cannot_directly_modify_stock(self):
        with self.assertRaises(PermissionDenied):
            move_stock(self.part.pk,'receive',D('2'),self.tech,'Mencoba')
        self.client.force_login(self.tech)
        self.assertEqual(self.client.post('/inventory/movement/', {'part':self.part.pk,'kind':'receive','quantity':'5','note':'Mencoba'}).status_code,403)
        self.part.refresh_from_db()
        self.assertEqual(self.part.current_qty,0)

    def test_invalid_issue_zero_amount(self):
        with self.assertRaises(ValidationError):
            move_stock(self.part.pk,'receive',D('0'),self.manager,'x')
        self.assertFalse(StockMovement.objects.exists())

    def test_request_from_mobile_and_wo(self):
        self.client.force_login(self.tech)
        response=self.client.post('/inventory/requests/new/',{'part':self.part.pk,'quantity':'3','order':self.wo.pk,'note':'Bearing macet'})
        self.assertEqual(response.status_code,302)
        obj=PartRequest.objects.get()
        self.assertEqual(obj.requested_by,self.tech)
        self.assertEqual(obj.order,self.wo)
        self.assertEqual(obj.status,'pending')
        self.assertEqual(self.part.current_qty,0)

    def test_other_workorder_cannot_be_referenced(self):
        self.client.force_login(self.other)
        response=self.client.post('/inventory/requests/new/',{'part':self.part.pk,'quantity':'3','order':self.wo.pk})
        self.assertEqual(response.status_code,200)
        self.assertFalse(PartRequest.objects.exists())

    def test_requests_private_to_technician(self):
        PartRequest.objects.create(part=self.part,quantity=D('2'),requested_by=self.tech)
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get('/inventory/requests/'),'BEARING-01')
        self.client.force_login(self.manager)
        self.assertContains(self.client.get('/inventory/requests/'),'BEARING-01')

    def test_review_then_fulfill_once(self):
        req=PartRequest.objects.create(part=self.part,quantity=D('2'),requested_by=self.tech)
        move_stock(self.part.pk,'receive',D('5'),self.manager,'Terima')
        review_request(req.pk,self.manager,'approve','Silakan')
        fulfill_request(req.pk,self.manager)
        req.refresh_from_db();self.part.refresh_from_db()
        self.assertEqual(req.status,'fulfilled')
        self.assertEqual(self.part.current_qty,D('3'))
        self.assertEqual(StockMovement.objects.filter(request=req).count(),1)
        with self.assertRaises(ValidationError): fulfill_request(req.pk,self.manager)
        self.part.refresh_from_db(); self.assertEqual(self.part.current_qty,D('3'))

    def test_approval_does_not_consume_stock(self):
        req=PartRequest.objects.create(part=self.part,quantity=D('2'),requested_by=self.tech)
        review_request(req.pk,self.manager,'approve','')
        self.part.refresh_from_db()
        self.assertEqual(self.part.current_qty,D('0'))
        with self.assertRaises(ValidationError): fulfill_request(req.pk,self.manager)
        req.refresh_from_db();self.assertEqual(req.status,'approved')

    def test_reject_requires_reason(self):
        req=PartRequest.objects.create(part=self.part,quantity=D('2'),requested_by=self.tech)
        with self.assertRaises(ValidationError):review_request(req.pk,self.manager,'reject','')
        req.refresh_from_db();self.assertEqual(req.status,'pending')

    def test_csrf_mandatory_for_mutation(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.manager)
        response=client.post('/inventory/movement/', {'part':self.part.pk,'kind':'receive','quantity':'5','note':'Dokumen'})
        self.assertEqual(response.status_code,403)
        self.assertFalse(StockMovement.objects.exists())

    def test_master_created_at_zero(self):
        self.client.force_login(self.manager)
        result=self.client.post('/inventory/parts/new/', {'sku':' belt02 ','name':'Sabuk motor','unit':'pcs','min_qty':'4','active':'on'})
        self.assertEqual(result.status_code,302)
        obj=Part.objects.get(sku='BELT02')
        self.assertEqual(obj.current_qty,0)

    def test_one_draft_opname_and_counts(self):
        move_stock(self.part.pk,'receive',D('8'),self.manager,'Awal')
        op=start_stocktake('Bulanan',self.manager)
        line=op.lines.get()
        self.assertEqual(line.book_qty,D('8'))
        with self.assertRaises(ValidationError): start_stocktake('Duplikat',self.manager)
        count_line(op.pk,line.pk,D('7'),self.manager)
        changes=post_stocktake(op.pk,self.manager)
        self.part.refresh_from_db();self.assertEqual(changes,1)
        self.assertEqual(self.part.current_qty,D('7'))
        self.assertEqual(StockMovement.objects.filter(stocktake=op).count(),1)

    def test_incomplete_count_cannot_post(self):
        op=start_stocktake('Siklus',self.manager)
        with self.assertRaises(ValidationError): post_stocktake(op.pk,self.manager)
        op.refresh_from_db();self.assertEqual(op.status,'draft')

    def test_stale_count_does_not_overwrite_live_movements(self):
        move_stock(self.part.pk,'receive',D('10'),self.manager,'Awal')
        op=start_stocktake('Fisik',self.manager)
        count_line(op.pk,op.lines.get().pk,D('8'),self.manager)
        move_stock(self.part.pk,'issue',D('1'),self.manager,'Dipakai selama hitung')
        with self.assertRaises(ValidationError): post_stocktake(op.pk,self.manager)
        self.part.refresh_from_db();self.assertEqual(self.part.current_qty,D('9'))
        self.assertFalse(StockMovement.objects.filter(stocktake=op).exists())

    def test_stocktake_does_not_change_maintenance(self):
        op=start_stocktake('Audit',self.manager)
        count_line(op.pk,op.lines.get().pk,D('0'),self.manager)
        post_stocktake(op.pk,self.manager)
        self.wo.refresh_from_db()
        self.assertEqual(self.wo.status,'open')
        self.assertEqual(self.wo.answers,[])

    def test_stocktake_rejects_second_post(self):
        op=start_stocktake('Audit',self.manager)
        count_line(op.pk,op.lines.get().pk,D('0'),self.manager)
        post_stocktake(op.pk,self.manager)
        with self.assertRaises(ValidationError):post_stocktake(op.pk,self.manager)

    def test_post_count_after_post_forbidden(self):
        op=start_stocktake('Audit',self.manager)
        line=op.lines.get()
        count_line(op.pk,line.pk,D('0'),self.manager)
        post_stocktake(op.pk,self.manager)
        with self.assertRaises(ValidationError):count_line(op.pk,line.pk,D('3'),self.manager)

    def test_technician_cannot_post_opname(self):
        op=start_stocktake('Audit',self.manager)
        with self.assertRaises(PermissionDenied):post_stocktake(op.pk,self.tech)

    def test_health_version_040(self):
        self.assertEqual(self.client.get('/healthz').json()['version'],'0.4.0')

    def test_sidebar_only_adds_inventory(self):
        self.client.force_login(self.tech)
        html=self.client.get('/').content.decode()
        self.assertIn('Stok sparepart',html)
        self.assertIn('Work order',html)

    def test_post_only_for_decision(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get('/inventory/requests/1/decide/').status_code,405)

    def test_stocktake_post_confirmation(self):
        op=start_stocktake('Audit',self.manager)
        self.client.force_login(self.manager)
        response=self.client.post(reverse('inventory_stocktake_post',args=[op.pk]), {'confirm':'NO'})
        self.assertEqual(response.status_code,302)
        op.refresh_from_db();self.assertEqual(op.status,'draft')

    def test_cancelled_count_preserves_audit_and_allows_new_session(self):
        op=start_stocktake('Audit gagal',self.manager)
        count_line(op.pk,op.lines.get().pk,D('3'),self.manager)
        cancel_stocktake(op.pk,self.manager,'Stok sudah berubah')
        op.refresh_from_db()
        self.assertEqual(op.status,'cancelled')
        self.assertEqual(op.lines.get().counted_qty,D('3'))
        self.assertEqual(self.part.current_qty,D('0'))
        again=start_stocktake('Ulang',self.manager)
        self.assertEqual(again.status,'draft')

    def test_cannot_cancel_posted_count(self):
        op=start_stocktake('Audit selesai',self.manager)
        count_line(op.pk,op.lines.get().pk,D('0'),self.manager)
        post_stocktake(op.pk,self.manager)
        with self.assertRaises(ValidationError):cancel_stocktake(op.pk,self.manager,'Tidak boleh')

    def test_cancel_requires_reason(self):
        op=start_stocktake('Audit gagal',self.manager)
        with self.assertRaises(ValidationError):cancel_stocktake(op.pk,self.manager,'')

    def test_manager_can_edit_minimum_without_changing_balance(self):
        move_stock(self.part.pk, 'receive', D('10'), self.manager, 'GRN awal')
        self.client.force_login(self.manager)
        res=self.client.post(reverse('inventory_edit_part',args=[self.part.pk]), {
            'sku':'BEARING-01','name':'Bearing jarum baru','machine_type':'Jahit',
            'unit':'pcs','location':'Rak 3','min_qty':'5.000','active':'on'})
        self.assertEqual(res.status_code,302)
        self.part.refresh_from_db()
        self.assertEqual(self.part.min_qty,D('5'))
        self.assertEqual(self.part.location,'Rak 3')
        self.assertEqual(self.part.current_qty,D('10'))
        self.assertEqual(StockMovement.objects.count(),1)

    def test_technician_cannot_edit_catalog(self):
        self.client.force_login(self.tech)
        self.assertEqual(self.client.get(reverse('inventory_edit_part',args=[self.part.pk])).status_code,403)
