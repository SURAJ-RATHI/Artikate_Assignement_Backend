from django.db import models

from .context import get_current_tenant


class Tenant(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=120)

    def __str__(self):
        return self.slug


class TenantQuerySet(models.QuerySet):
    pass


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):
    def get_queryset(self):
        queryset = super().get_queryset()
        tenant = get_current_tenant()
        if tenant is None:
            return queryset.none()
        return queryset.filter(tenant=tenant)


class TenantScopedOrder(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    reference = models.CharField(max_length=40)
    amount_cents = models.PositiveIntegerField()

    objects = TenantManager()
    unscoped = models.Manager()

    class Meta:
        indexes = [models.Index(fields=["tenant", "reference"])]
