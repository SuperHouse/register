import datetime
import zoneinfo

from django.conf import settings
from django.db import models
from django.utils import timezone


# A special time (essentially pi), to use which suppresses the time on a datetime.
# If you're still awake at this time and doing stuff, go home!
tz = zoneinfo.ZoneInfo(settings.TIME_ZONE)
witching_hour = datetime.time(3, 14, 15, 9, tzinfo=tz)


# Return a string representation of a date and time in the local timezone for use in templates.
# Dates imported with no times will have a time of 4:20am.  In this case, we return just the date.
def get_dt_as_string(dt):
    if dt.tzinfo == datetime.timezone.utc:
        dt = dt.astimezone(tz)
    if dt.time() == witching_hour:
        return dt.strftime('%-d %b %Y')
    else:
        return dt.strftime('%-d %b %Y, %H:%M:%S')


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
    price = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    price2 = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['sku', 'hw_version'], name='unique_sku_hwversion')]

    def __str__(self):
        return f'{self.sku}: {self.name} {self.hw_version}'


class Device(models.Model):
    design = models.ForeignKey(Design, on_delete=models.PROTECT)
    assembly_date = models.DateField(default=timezone.localdate)
    sw_version = models.CharField(max_length=20, null=True, blank=True)
    invoice = models.CharField(max_length=20, null=True, blank=True)
    # We may need to change notes to a TextField if we need multi-line
    notes = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f'{self.design.sku} {self.design.hw_version} (sn: {self.pk})'

    @classmethod
    def first_free_serial(self):
        return Device.objects.aggregate(models.Max('pk'))['pk__max'] + 1


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
    test_dt = models.DateTimeField(default=timezone.now)
    result = models.CharField(max_length=20, choices=RESULT_CHOICES, default='NEW')
    notes = models.TextField(null=True, blank=True)

    __test__ = False  # Stop PyTest from treating this model as a test class.

    class Meta:
        ordering = ["test_dt"]

    def __str__(self):
        tzname = settings.TIME_ZONE
        if tzname:
            tz = zoneinfo.ZoneInfo(tzname)
            test_dt_as_local_str = str(self.test_dt.astimezone(tz))  # .strftime('%Y-%m-%d %H:%M:%S %Z')
        else:
            test_dt_as_local_str = str(self.test_dt)

        return f'{self.device} - {test_dt_as_local_str} - {self.result}'

    def get_bootstrap_table_class(self):
        classes = {
            self.NEW: 'table-light',
            self.PASS: 'table-success',
            self.FAIL: 'table-danger',
            self.INCONCLUSIVE: 'table-warning',
        }

        return classes.get(self.result, 'table-dark')

    def get_test_dt_as_string(self):
        return get_dt_as_string(self.test_dt)


class TestImage(models.Model):
    test_record = models.ForeignKey(TestRecord, on_delete=models.CASCADE)
    image = models.ImageField()

    def __str__(self):
        return f'{self.test_record} - {self.image}'


class DeviceEvent(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    event_dt = models.DateTimeField(verbose_name='When', default=timezone.now)
    # Types is free-form, except for some agreed values: ("NOTE", "SHIP", "INV")
    event_type = models.CharField(max_length=50, default="NOTE")
    internal = models.BooleanField(default=False, help_text='Do not show this event to clients')
    description = models.TextField()

    class Meta:
        ordering = ["device__id", "event_dt"]

    def __str__(self):
        return f'{self.device}@{self.event_dt}: ({self.event_type}): {self.description}'

    def get_event_type_icon(self):
        icons = {
            'NOTE': '📝',
            'SHIP': '🚢',
            'INV': '🧾',
        }

        return icons.get(self.event_type, '🤷')

    def get_event_dt_as_string(self):
        return get_dt_as_string(self.event_dt)
