"""Regression tests for release 0.4.3. Independent of live DB and customer data."""
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from .models import Part, PartRequest, StockImportBatch, StockMovement
from .services import (make_request, review_request, move_stock, is_stock_admin,
                       is_sparepart_manager, route_for_requester, import_stock_rows)
from .forms import RequestForm
from .importing import read_csv, read_xlsx, normalize

class Inventory043Tests(TestCase):
    def setUp(self):
        U=get_user_model()
        self.tech=U.objects.create_user('tech-043',password='only-testing-12345')
        self.admin=U.objects.create_user('stock-043',password='only-testing-12345')
        self.manager=U.objects.create_user('manager-043',password='only-testing-12345')
        self.other=U.objects.create_user('other-043',password='only-testing-12345')
        self.superuser=U.objects.create_superuser('root-043',password='only-testing-12345')
        self.admin.groups.add(Group.objects.get(name='Pengelola Stok Sparepart'))
        self.manager.groups.add(Group.objects.get(name='Manager Sparepart'))
        self.part=Part.objects.create(sku='001',name='Pisau Gerber HX',unit='pcs',min_qty=2)

    def upload(self, content, filename='stock.csv'):
        self.client.force_login(self.admin)
        return self.client.post(reverse('inventory_import_movements'), {
            'file':SimpleUploadedFile(filename,content)})

    def test_request_routes_and_separation_of_duties(self):
        self.assertEqual(route_for_requester(self.tech),'stock_admin')
        self.assertEqual(route_for_requester(self.admin),'manager')
        self.assertTrue(is_stock_admin(self.admin))
        self.assertTrue(is_sparepart_manager(self.manager))
        tech_req=PartRequest.objects.create(part=self.part,quantity=1,requested_by=self.tech,
                                            approval_route='stock_admin')
        admin_req=PartRequest.objects.create(part=self.part,quantity=1,requested_by=self.admin,
                                             approval_route='manager')
        with self.assertRaises(PermissionDenied):review_request(tech_req.pk,self.manager,'approve','')
        with self.assertRaises(PermissionDenied):review_request(tech_req.pk,self.tech,'approve','')
        review_request(tech_req.pk,self.admin,'approve','')
        with self.assertRaises(PermissionDenied):review_request(admin_req.pk,self.admin,'approve','')
        with self.assertRaises(PermissionDenied):review_request(admin_req.pk,self.tech,'approve','')
        review_request(admin_req.pk,self.manager,'approve','')
        tech_req.refresh_from_db();admin_req.refresh_from_db()
        self.assertEqual(tech_req.status,'approved')
        self.assertEqual(admin_req.status,'approved')
        self.assertEqual(StockMovement.objects.count(),0)

    def test_manager_cannot_mutate_stock_without_admin_role(self):
        with self.assertRaises(PermissionDenied):move_stock(self.part.pk,'receive',Decimal('3'),self.manager,'x')
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(reverse('inventory_movement')).status_code,403)
        self.assertEqual(self.client.get(reverse('inventory_import_movements')).status_code,403)

    def test_integer_fields_and_no_fraction_new_transactions(self):
        self.client.force_login(self.admin)
        invalid=self.client.post(reverse('inventory_movement'),{
            'part':self.part.pk,'kind':'receive','quantity':'2.5','note':'GRN'})
        self.assertEqual(invalid.status_code,200)
        self.assertFalse(StockMovement.objects.exists())
        with self.assertRaises(ValidationError):move_stock(self.part.pk,'receive',Decimal('2.5'),self.admin,'GRN')
        self.part.refresh_from_db();self.assertEqual(self.part.current_qty,0)
        reqform=RequestForm({'part':self.part.pk,'quantity':'1.5','note':'Tidak valid'},user=self.tech)
        self.assertFalse(reqform.is_valid())
        self.assertFalse(PartRequest.objects.exists())
        self.assertContains(self.client.get(reverse('inventory_overview')),'0')

    def test_csv_bulk_atomic_and_duplicate_upload(self):
        body=b'kode_sparepart,jenis,jumlah,referensi\n001,masuk,12,GRN-A\n001,keluar,2,WO-13\n'
        self.assertEqual(self.upload(body).status_code,302)
        self.part.refresh_from_db();self.assertEqual(self.part.current_qty,10)
        self.assertEqual(StockMovement.objects.count(),2)
        self.assertEqual(StockImportBatch.objects.count(),1)
        self.assertEqual(self.upload(body).status_code,200)
        self.part.refresh_from_db();self.assertEqual(self.part.current_qty,10)
        self.assertEqual(StockMovement.objects.count(),2)

    def test_import_bad_last_row_never_changes_stock(self):
        body=b'kode_sparepart,jenis,jumlah,referensi\n001,masuk,8,PO-1\nMISSING,keluar,1,PO-2\n'
        self.assertEqual(self.upload(body).status_code,200)
        self.part.refresh_from_db();self.assertEqual(self.part.current_qty,0)
        self.assertFalse(StockMovement.objects.exists())
        self.assertFalse(StockImportBatch.objects.exists())

    def test_import_rejects_insufficient_stock_and_decimal(self):
        body=b'kode_sparepart,jenis,jumlah,referensi\n001,masuk,8,PO-1\n001,keluar,9,WO-1\n'
        self.assertEqual(self.upload(body).status_code,200)
        self.assertFalse(StockMovement.objects.exists())
        with self.assertRaises(ValidationError):read_csv(b'kode_sparepart,jenis,jumlah,referensi\n001,masuk,1.5,PO-1\n')

    def test_import_xlsx(self):
        from openpyxl import Workbook
        import io
        book=Workbook();sheet=book.active;sheet.title='Mutasi'
        sheet.append(['kode_sparepart','jenis','jumlah','referensi'])
        sheet.append(['001','masuk',3,'GRN-XL'])
        buff=io.BytesIO();book.save(buff)
        self.assertEqual(self.upload(buff.getvalue(),'stock.xlsx').status_code,302)
        self.part.refresh_from_db();self.assertEqual(self.part.current_qty,3)

    def test_manual_import_requires_group(self):
        self.client.force_login(self.tech)
        self.assertEqual(self.client.get(reverse('inventory_import_movements')).status_code,403)
        self.assertEqual(self.client.get(reverse('inventory_movement_template_xlsx')).status_code,403)

    def test_no_self_approval_even_with_both_groups(self):
        self.manager.groups.add(Group.objects.get(name='Pengelola Stok Sparepart'))
        req=PartRequest.objects.create(part=self.part,quantity=1,requested_by=self.manager,approval_route='manager')
        with self.assertRaises(PermissionDenied):review_request(req.pk,self.manager,'approve','')
