from django.db import connection
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext

from tenancy.context import tenant_context
from tenancy.models import Tenant

from .models import Customer, Order, OrderLine, Product
from .views import order_summary_broken, order_summary_fixed


class OrderSummaryQueryTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(slug="acme", name="Acme")
        customer = Customer.objects.create(tenant=self.tenant, email="ops@acme.test", name="Ops")
        products = [
            Product.objects.create(tenant=self.tenant, sku=f"SKU-{index}", name=f"Product {index}")
            for index in range(3)
        ]
        for order_index in range(25):
            order = Order.objects.create(tenant=self.tenant, customer=customer, status="paid")
            for line_index in range(3):
                OrderLine.objects.create(
                    order=order,
                    product=products[line_index],
                    quantity=1 + line_index,
                    unit_price_cents=1000 + order_index,
                )

    def test_fixed_view_removes_n_plus_one_queries(self):
        request = RequestFactory().get("/api/orders/summary/")

        with tenant_context(self.tenant):
            with CaptureQueriesContext(connection) as broken_queries:
                order_summary_broken(request)
            with CaptureQueriesContext(connection) as fixed_queries:
                order_summary_fixed(request)

        self.assertGreater(len(broken_queries), 70)
        self.assertLessEqual(len(fixed_queries), 4)
