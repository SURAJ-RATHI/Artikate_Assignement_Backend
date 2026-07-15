from django.db.models import Count, Prefetch, Sum
from django.http import JsonResponse

from tenancy.context import get_current_tenant

from .models import Order, OrderLine


def order_summary_broken(request):
    tenant = get_current_tenant()
    orders = Order.objects.filter(tenant=tenant).order_by("-created_at")[:250]

    rows = []
    total_cents = 0
    for order in orders:
        line_items = []
        for line in order.lines.all():
            total_cents += line.total_cents
            line_items.append(
                {
                    "sku": line.product.sku,
                    "quantity": line.quantity,
                    "total_cents": line.total_cents,
                }
            )
        rows.append(
            {
                "id": order.id,
                "customer_email": order.customer.email,
                "status": order.status,
                "lines": line_items,
            }
        )

    return JsonResponse({"orders": rows, "total_cents": total_cents})


def order_summary_fixed(request):
    tenant = get_current_tenant()
    lines = OrderLine.objects.select_related("product")
    orders = (
        Order.objects.filter(tenant=tenant)
        .select_related("customer")
        .prefetch_related(Prefetch("lines", queryset=lines))
        .annotate(line_count=Count("lines"), order_total_cents=Sum("lines__unit_price_cents"))
        .order_by("-created_at")[:250]
    )

    rows = []
    total_cents = 0
    for order in orders:
        line_items = []
        for line in order.lines.all():
            total_cents += line.total_cents
            line_items.append(
                {
                    "sku": line.product.sku,
                    "quantity": line.quantity,
                    "total_cents": line.total_cents,
                }
            )
        rows.append(
            {
                "id": order.id,
                "customer_email": order.customer.email,
                "status": order.status,
                "line_count": order.line_count,
                "lines": line_items,
            }
        )

    return JsonResponse({"orders": rows, "total_cents": total_cents})
