from django.contrib import admin
from django.urls import include, path

from orders.views import order_summary_broken, order_summary_fixed

urlpatterns = [
    path("__debug__/", include("debug_toolbar.urls")),
    path("admin/", admin.site.urls),
    path("api/orders/summary/broken/", order_summary_broken),
    path("api/orders/summary/", order_summary_fixed),
]
