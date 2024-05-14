from datetime import date, datetime

from django.conf import settings
from django.db import models


class Client(models.Model):
    company_name = models.CharField(max_length=255)
    logo = models.ImageField(null=True, blank=True)
    users = models.ManyToManyField(settings.AUTH_USER_MODEL)

    def __str__(self):
        return self.company_name


class Design(models.Model):
    client = models.ForeignKey(Client, on_delete=models.PROTECT)
    sku = models.CharField(verbose_name='SKU', max_length=50)
    name = models.CharField(max_length=255)
    hw_version = models.CharField(max_length=20)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.sku


class Device(models.Model):
    design = models.ForeignKey(Design, on_delete=models.PROTECT)
    assembly_date = models.DateField(default=date.today)
    sw_version = models.CharField(max_length=20, null=True, blank=True)
    # We may need to change notes to a TextField if we need multi-line
    notes = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f'{self.design.sku} (sn: {self.pk})'


class TestRecord(models.Model):
    NEW = 'NEW'
    PASS = 'PASS'
    FAIL = 'FAIL'
    INCONCLUSIVE = 'HUH?'

    RESULT_CHOICES = [
        (NEW, 'STARTED'),
        (PASS, 'PASSED'),
        (FAIL, 'FAILED'),
        (INCONCLUSIVE, 'INCONCLUSIVE'),
    ]
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    test_dt = models.DateTimeField(default=datetime.now)
    result = models.CharField(max_length=5, choices=RESULT_CHOICES, default='NEW')
    notes = models.TextField(null=True, blank=True)

    def __str__(self):
        return f'{self.device} - {self.test_dt} - {self.result}'

    def get_bootstrap_table_class(self):
        classes = {
            self.NEW: 'table-light',
            self.PASS: 'table-success',
            self.FAIL: 'table-danger',
            self.INCONCLUSIVE: 'table-warning',
        }

        return classes.get(self.result, 'table-dark')



