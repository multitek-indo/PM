"""Search UI regression tests; do not change inventory transactions or roles."""
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import Part, StockMovement


class MovementPartSearchTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.manager = user_model.objects.create_superuser(
            username='part-search-manager', email='part-search@example.invalid', password='isolated-test-only-123456789')
        self.tech = user_model.objects.create_user(
            username='part-search-tech', password='isolated-test-only-123456789')
        for number in range(120):
            Part.objects.create(sku=f'SP-{number:04d}', name=f'Pisau gerber {number}', active=True)
        self.first = Part.objects.get(sku='SP-0099')

    def test_search_only_on_stock_movement_form(self):
        self.client.force_login(self.manager)
        page = self.client.get(reverse('inventory_movement'))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'Cari sparepart berdasarkan kode atau nama')
        self.assertContains(page, 'pm-part-search.js')
        self.assertContains(page, 'SP-0099 - Pisau gerber 99')
        self.assertContains(page, 'name="part"')
        self.assertNotContains(self.client.get(reverse('inventory_request_new')), 'pm-part-search.js')
        self.assertNotContains(self.client.get(reverse('inventory_add_part')), 'pm-part-search.js')

    def test_normal_stock_mutation_unchanged(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse('inventory_movement'), {
            'part': str(self.first.pk), 'kind': 'receive', 'quantity': '3', 'note': 'Barang diterima UJI'
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(StockMovement.objects.count(), 1)
        self.first.refresh_from_db()
        self.assertEqual(self.first.current_qty, Decimal('3.000'))

    def test_invalid_submission_keeps_selected_option(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse('inventory_movement'), {
            'part': str(self.first.pk), 'kind': 'receive', 'quantity': '', 'note': 'Dokumen UJI'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'pm-part-search.js')
        self.assertEqual(str(response.context['form']['part'].value()), str(self.first.pk))
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_part_id_still_validated_server_side(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse('inventory_movement'), {
            'part': '999999999', 'kind': 'receive', 'quantity': '1', 'note': 'UJI'
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_technician_cannot_access_form(self):
        self.client.force_login(self.tech)
        self.assertEqual(self.client.get(reverse('inventory_movement')).status_code, 403)
        self.assertEqual(StockMovement.objects.count(), 0)
