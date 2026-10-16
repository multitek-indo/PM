"""0.4.4 accounting invariants. Runs with full Django suite on isolated DB."""
import io
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from openpyxl import Workbook
from .forms import RequestForm
from .importing import read_csv, read_xlsx
from .models import Part, PartRequest, StockMovement, StockImportBatch, ManualStockRequest, InventoryAudit
from .services import (move_stock, make_request, review_request, fulfill_request, cancel_request, return_issued,
                       import_stock_rows, review_import, propose_manual, review_manual, start_stocktake,
                       count_line, post_stocktake, is_sparepart_manager)
D=Decimal

class Ledger044Tests(TestCase):
    def setUp(self):
        U=get_user_model()
        self.super=U.objects.create_superuser('root44',password='only-tests-123456')
        self.tech=U.objects.create_user('technician44',password='only-tests-123456')
        self.store=U.objects.create_user('store44',password='only-tests-123456')
        self.manager=U.objects.create_user('manager44',password='only-tests-123456')
        self.both=U.objects.create_user('both44',password='only-tests-123456')
        self.tech.groups.add(Group.objects.get_or_create(name='Teknisi PM')[0])
        self.store.groups.add(Group.objects.get(name='Pengelola Stok Sparepart'))
        self.manager.groups.add(Group.objects.get(name='Manager Sparepart'))
        for name in ('Manager Sparepart','Pengelola Stok Sparepart'):
            self.both.groups.add(Group.objects.get(name=name))
        self.part=Part.objects.create(sku='44-001',name='Bearing',unit='pcs',min_qty=2)
        move_stock(self.part.pk,'receive',10,self.super,'Seed audit')

    def form(self,user,qty=2):
        f=RequestForm({'part':self.part.pk,'quantity':str(qty),'note':'Kebutuhan PM'},user=user)
        self.assertTrue(f.is_valid(),f.errors)
        return f

    def balance(self):
        self.part.refresh_from_db();return self.part.current_qty

    def test_technician_submit_debit_reject_refund_once(self):
        req=make_request(self.form(self.tech,3),self.tech)
        self.assertEqual(req.request_type,'consumption')
        self.assertEqual(self.balance(),7)
        review_request(req.pk,self.store,'reject','Tidak sesuai spesifikasi')
        self.assertEqual(self.balance(),10)
        with self.assertRaises(ValidationError):review_request(req.pk,self.store,'reject','ulang')
        self.assertEqual(StockMovement.objects.filter(request=req).count(),2)
        self.assertEqual(self.balance(),10)

    def test_technician_no_negative_and_full_approval_no_extra_debit(self):
        with self.assertRaises(ValidationError):make_request(self.form(self.tech,11),self.tech)
        self.assertEqual(self.balance(),10)
        req=make_request(self.form(self.tech,8),self.tech)
        with self.assertRaises(ValidationError):make_request(self.form(self.tech,3),self.tech)
        review_request(req.pk,self.store,'approve','OK')
        fulfill_request(req.pk,self.store)
        self.assertEqual(self.balance(),2)
        with self.assertRaises(ValidationError):fulfill_request(req.pk,self.store)
        self.assertEqual(StockMovement.objects.filter(request=req).count(),1)

    def test_replenishment_manager_approve_credit_once_and_never_issue(self):
        req=make_request(self.form(self.store,30),self.store)
        self.assertEqual(req.request_type,'replenishment')
        self.assertEqual(self.balance(),10)
        with self.assertRaises(PermissionDenied):review_request(req.pk,self.store,'approve','')
        review_request(req.pk,self.manager,'approve','Disetujui sebagai penerimaan administratif')
        self.assertEqual(self.balance(),40)
        req.refresh_from_db();self.assertEqual(req.status,'fulfilled')
        with self.assertRaises(ValidationError):review_request(req.pk,self.manager,'approve','ulang')
        with self.assertRaises(ValidationError):fulfill_request(req.pk,self.store)
        self.assertEqual(StockMovement.objects.filter(request=req).count(),1)

    def test_handover_partial_cancel_returns_only_unused(self):
        req=make_request(self.form(self.tech,5),self.tech)
        review_request(req.pk,self.store,'approve','')
        fulfill_request(req.pk,self.store,2)
        self.assertEqual(self.balance(),5)
        cancel_request(req.pk,self.tech,'Sisa tidak diperlukan')
        self.assertEqual(self.balance(),8)
        with self.assertRaises(ValidationError):cancel_request(req.pk,self.tech,'ulang')
        return_issued(req.pk,self.store,1,'Diterima fisik dalam kondisi baik')
        self.assertEqual(self.balance(),9)
        with self.assertRaises(ValidationError):return_issued(req.pk,self.store,2,'melebihi issued')

    def test_legacy_approved_technician_debits_only_on_handover(self):
        req=PartRequest.objects.create(part=self.part,quantity=3,requested_by=self.tech,approval_route='stock_admin',request_type='consumption',ledger_phase='legacy',status='approved')
        self.assertEqual(self.balance(),10)
        fulfill_request(req.pk,self.store)
        self.assertEqual(self.balance(),7)
        self.assertEqual(StockMovement.objects.filter(request=req).count(),1)

    def test_import_semantic_duplicates_and_manager_approval(self):
        rows=read_csv(b'kode_sparepart,jenis,jumlah,referensi\n44-001,masuk,3,GRN44\n')
        batch=import_stock_rows(rows,'a'*64,'first.csv',self.store,document_id='GRN44')
        self.assertEqual(self.balance(),10)
        with self.assertRaises(ValidationError):import_stock_rows(rows,'b'*64,'second.csv',self.store,document_id='GRN45')
        with self.assertRaises(PermissionDenied):review_import(batch.pk,self.store,'approve','')
        review_import(batch.pk,self.manager,'approve','OK')
        self.assertEqual(self.balance(),13)
        with self.assertRaises(ValidationError):review_import(batch.pk,self.manager,'approve','Again')

    def test_import_stale_stock_fails_atomically(self):
        rows=read_csv(b'kode_sparepart,jenis,jumlah,referensi\n44-001,keluar,14,WO44\n')
        batch=import_stock_rows(rows,'c'*64,'out.csv',self.store,'ISS44')
        with self.assertRaises(ValidationError):review_import(batch.pk,self.manager,'approve','')
        self.assertEqual(self.balance(),10)
        self.assertEqual(StockMovement.objects.filter(import_batch=batch).count(),0)

    def test_manual_separated_approval(self):
        manual=propose_manual(self.part.pk,'issue',3,'OUT44',self.store,'Pemakaian khusus tercatat')
        self.assertEqual(self.balance(),10)
        with self.assertRaises(PermissionDenied):review_manual(manual.pk,self.store,'approve','')
        review_manual(manual.pk,self.manager,'approve','OK')
        self.assertEqual(self.balance(),7)
        with self.assertRaises(ValidationError):review_manual(manual.pk,self.manager,'approve','again')
        self.assertTrue(InventoryAudit.objects.filter(entity_type='manual',action='approve').exists())

    def test_stocktake_distinct_manager_and_counter(self):
        op=start_stocktake('Audit real',self.store)
        count_line(op.pk,op.lines.first().pk,9,self.store)
        with self.assertRaises(PermissionDenied):post_stocktake(op.pk,self.store)
        post_stocktake(op.pk,self.manager)
        self.assertEqual(self.balance(),9)
        with self.assertRaises(ValidationError):post_stocktake(op.pk,self.manager)

    def test_manager_read_only_dashboard_stocktake_and_orders(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(reverse('inventory_stocktakes')).status_code,200)
        self.assertEqual(self.client.get(reverse('inventory_movement')).status_code,403)
        self.assertEqual(self.client.get(reverse('inventory_procurement_export')).status_code,200)
        self.assertEqual(self.client.get(reverse('inventory_audit')).status_code,200)

    def test_non_stock_supervisor_not_mutate(self):
        U=get_user_model();supervisor=U.objects.create_user('supervisor44')
        supervisor.groups.add(Group.objects.get_or_create(name='Supervisor PM')[0])
        self.client.force_login(supervisor)
        self.assertEqual(self.client.get(reverse('inventory_movement')).status_code,403)
        self.assertEqual(self.client.get(reverse('inventory_stocktake_new')).status_code,403)
        self.assertEqual(self.client.get(reverse('inventory_import_movements')).status_code,403)

    def test_xlsx_bad_dimensions_does_not_skip_last_row(self):
        wb=Workbook();ws=wb.active;ws.title='Mutasi'
        ws.append(['kode_sparepart','jenis','jumlah','referensi'])
        ws.append(['44-001','masuk',2,'PO-A'])
        ws.append(['44-001','masuk',3,'PO-B'])
        content=io.BytesIO();wb.save(content)
        data=content.getvalue()
        # Parser always resets dimensions and sees both rows.
        self.assertEqual(len(read_xlsx(data)),2)

    def test_manager_cannot_approve_self_with_two_groups(self):
        req=make_request(self.form(self.both,1),self.both)
        with self.assertRaises(PermissionDenied):review_request(req.pk,self.both,'approve','')

    def test_manager_only_cannot_request_or_post_manually(self):
        with self.assertRaises(PermissionDenied):make_request(self.form(self.manager,2),self.manager)
        with self.assertRaises(PermissionDenied):propose_manual(self.part.pk,'receive',2,'PR-44',self.manager,'Tidak boleh')

    def test_movement_database_guards_math(self):
        from django.db import IntegrityError,transaction
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StockMovement.objects.create(part=self.part,kind='receive',qty_delta=2,before_qty=10,after_qty=99,actor=self.super)
        self.assertEqual(self.balance(),10)

    def test_procurement_report_contains_document_and_price(self):
        form=RequestForm({'part':self.part.pk,'quantity':'3','note':'Jaga minimum stok','procurement_ref':'PO-044','supplier':'Vendor A','estimated_unit_price':'12500.00'},user=self.store)
        self.assertTrue(form.is_valid(),form.errors)
        req=make_request(form,self.store)
        self.assertEqual(req.estimated_unit_price,D('12500'))
        self.client.force_login(self.manager)
        body=self.client.get(reverse('inventory_procurement_export')).content.decode('utf-8-sig')
        self.assertIn('PO-044',body);self.assertIn('Vendor A',body)

    def test_business_duplicate_even_when_line_order_swaps(self):
        rows=read_csv(b'kode_sparepart,jenis,jumlah,referensi\n44-001,masuk,2,GRN2\n44-001,masuk,3,GRN3\n')
        import_stock_rows(rows,'d'*64,'a.csv',self.store,'DOC44A')
        with self.assertRaises(ValidationError):
            import_stock_rows(list(reversed(rows)),'e'*64,'b.csv',self.store,'DOC44B')

    def test_inventory_admin_master_update_preserves_balance(self):
        self.client.force_login(self.store)
        page=reverse('inventory_edit_part',args=[self.part.pk])
        resp=self.client.post(page,{'sku':self.part.sku,'name':'Bearing revisi','machine_type':'','unit':'pcs','location':'Rak B','min_qty':'2','active':'on'})
        self.assertEqual(resp.status_code,302)
        self.assertEqual(self.balance(),10)
        self.assertTrue(InventoryAudit.objects.filter(entity_type='part',action='edited').exists())
