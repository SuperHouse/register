from datetime import date

from django.db import models

class Client(models.Model):
    company_name = models.CharField(max_length=255)
    logo = models.ImageField(null=True, blank=True)

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


"""
After import, assembly_date can be converted to YYYY-MM-DD format using the following sqlite code:
UPDATE device_device
SET assembly_date = 
    substr(assembly_date, -4) || '-' || 
    CASE substr(assembly_date, instr(assembly_date, '-') + 1, 3)
        WHEN 'Jan' THEN '01'
        WHEN 'Feb' THEN '02'
        WHEN 'Mar' THEN '03'
        WHEN 'Apr' THEN '04'
        WHEN 'May' THEN '05'
        WHEN 'Jun' THEN '06'
        WHEN 'Jul' THEN '07'
        WHEN 'Aug' THEN '08'
        WHEN 'Sep' THEN '09'
        WHEN 'Oct' THEN '10'
        WHEN 'Nov' THEN '11'
        WHEN 'Dec' THEN '12'
    END || '-' ||
    substr('0' || substr(assembly_date, 1, instr(assembly_date, '-') - 1), -2);
"""
