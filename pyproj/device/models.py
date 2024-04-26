from datetime import date

from django.conf import settings
from django.db import models


class Client(models.Model):
    company_name = models.CharField(max_length=255)
    logo = models.ImageField(null=True, blank=True)
    user = models.ManyToManyField(settings.AUTH_USER_MODEL)

    def __str__(self):
        return self.company_name


class Design(models.Model):
    client = models.ForeignKey(Client, on_delete=models.PROTECT)
    sku = models.CharField(verbose_name='SKU', max_length=50)
    name = models.CharField(max_length=255)
    version = models.CharField(max_length=20)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.sku


class Device(models.Model):
    design = models.ForeignKey(Design, on_delete=models.PROTECT)
    assembly_date = models.DateField(default=date.today)
    # We may need to change notes to a TextField if we need multi-line
    notes = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f'{self.design.sku} (sn: {self.pk})'
