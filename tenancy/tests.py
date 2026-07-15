from django.test import TestCase

from .context import tenant_context
from .models import Tenant, TenantScopedOrder


class TenantManagerTests(TestCase):
    def setUp(self):
        self.tenant_a = Tenant.objects.create(slug="tenant-a", name="Tenant A")
        self.tenant_b = Tenant.objects.create(slug="tenant-b", name="Tenant B")
        TenantScopedOrder.unscoped.create(tenant=self.tenant_a, reference="A-001", amount_cents=1200)
        TenantScopedOrder.unscoped.create(tenant=self.tenant_b, reference="B-001", amount_cents=900)

    def test_all_is_scoped_to_current_tenant(self):
        with tenant_context(self.tenant_a):
            self.assertEqual(list(TenantScopedOrder.objects.values_list("reference", flat=True)), ["A-001"])

    def test_filter_and_get_do_not_leak_other_tenant_rows(self):
        with tenant_context(self.tenant_a):
            self.assertFalse(TenantScopedOrder.objects.filter(reference="B-001").exists())
            with self.assertRaises(TenantScopedOrder.DoesNotExist):
                TenantScopedOrder.objects.get(reference="B-001")

    def test_no_tenant_context_returns_empty_queryset(self):
        self.assertEqual(TenantScopedOrder.objects.count(), 0)
