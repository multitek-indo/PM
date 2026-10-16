"""Regression checks for selectable search on movement page, not stock logic."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import Part, StockMovement


class PartSearchSelectionV042Tests(TestCase):
    def setUp(self):
        manager = get_user_model().objects.create_superuser(
            username='picker-manager', email='picker@example.invalid', password='isolated-test-only-123456')
        self.client.force_login(manager)
        self.part = Part.objects.create(sku='TEST-PICKER', name='Pisau gerber HX', active=True)

    def test_movement_has_clickable_search_containers(self):
        response = self.client.get(reverse('inventory_movement'))
        self.assertEqual(response.status_code, 200)
        for snippet in ('inv-part-choices', 'inv-part-picked', 'pm-part-search.js', '?v=042'):
            self.assertContains(response, snippet)
        self.assertContains(response, 'name="part"')

    def test_search_ui_not_added_to_other_inventory_forms(self):
        for page in ('inventory_add_part', 'inventory_request_new'):
            response = self.client.get(reverse(page))
            self.assertNotContains(response, 'pm-part-search.js')

    def test_posted_part_id_still_works(self):
        response = self.client.post(reverse('inventory_movement'), {
            'part': str(self.part.pk), 'kind': 'receive',
            'quantity': '2', 'note': 'Regresi UI picker saja',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(StockMovement.objects.count(), 1)

    def test_search_text_not_accepted_as_part_identifier(self):
        response = self.client.post(reverse('inventory_movement'), {
            'part': 'Pisau gerber HX', 'kind': 'receive',
            'quantity': '2', 'note': 'Regresi keamanan',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(StockMovement.objects.count(), 0)
