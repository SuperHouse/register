from django.db import models

class Client(models.Model):
    company_name = models.CharField(max_length=255)
    logo = models.ImageField(null=True, blank=True)

    def __str__(self):
        return self.company_name


