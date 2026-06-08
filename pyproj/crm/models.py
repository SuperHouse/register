from django.conf import settings
from django.db import models


class Client(models.Model):
    company_name = models.CharField(max_length=255)
    logo = models.ImageField(upload_to='clients/', null=True, blank=True)
    users = models.ManyToManyField(settings.AUTH_USER_MODEL)
    api_key = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return self.company_name
