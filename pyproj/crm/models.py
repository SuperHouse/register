from django.conf import settings
from django.db import models


class Org(models.Model):
    company_name = models.CharField(max_length=255)
    logo = models.ImageField(upload_to='clients/', null=True, blank=True)
    users = models.ManyToManyField(settings.AUTH_USER_MODEL)

    is_client = models.BooleanField(default=True)
    is_manufacturer = models.BooleanField(default=False)
    is_supplier = models.BooleanField(default=False)


    def __str__(self):
        return self.company_name

    @classmethod
    def get_clients(cls):
        return cls.objects.filter(is_client=True)

    @classmethod
    def get_manufacturers(cls):
        return cls.objects.filter(is_manufacturer=True)

    @classmethod
    def get_suppliers(cls):
        return cls.objects.filter(is_supplier=True)

