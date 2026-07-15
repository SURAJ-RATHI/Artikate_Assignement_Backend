from django.core.exceptions import SuspiciousOperation

from .context import reset_current_tenant, set_current_tenant
from .models import Tenant


class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant = self._tenant_from_request(request)
        token = set_current_tenant(tenant)
        request.tenant = tenant
        try:
            return self.get_response(request)
        finally:
            reset_current_tenant(token)

    def _tenant_from_request(self, request):
        slug = request.headers.get("X-Tenant-Slug")
        if not slug:
            host = request.get_host().split(":")[0]
            parts = host.split(".")
            if len(parts) > 2:
                slug = parts[0]

        if not slug:
            return None

        try:
            return Tenant.objects.get(slug=slug)
        except Tenant.DoesNotExist:
            raise SuspiciousOperation("Unknown tenant")
