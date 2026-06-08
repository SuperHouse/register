# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
import datetime
import os
import zoneinfo

from django.conf import settings
from django.db import models
from django.utils import timezone

from crm.models import Client

# A special time (essentially pi), to use which suppresses the time on a datetime.
# If you're still awake at this time and doing stuff, go home!
tz = zoneinfo.ZoneInfo(settings.TIME_ZONE)
witching_hour = datetime.time(3, 14, 15, 9, tzinfo=tz)


# Return a string representation of a date and time in the local timezone for use in templates.
# Dates imported with no times will use the witching hour (see above) as a time.
# In this case, we return just the date.
def get_dt_as_string(dt):
    if dt.tzinfo == datetime.timezone.utc:
        dt = dt.astimezone(tz)
    if dt.time() == witching_hour:
        return dt.strftime('%-d-%b-%Y')
    else:
        return dt.strftime('%-d-%b-%Y %H:%M:%S')


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
    creation_dt = models.DateTimeField(default=timezone.now)
    invoice = models.CharField(max_length=20, null=True, blank=True)
    po = models.CharField('Purchase order', max_length=20, null=True, blank=True)
    # We may need to change notes to a TextField if we need multi-line
    notes = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f'{self.design.sku} {self.design.hw_version} (sn: {self.pk})'

    @classmethod
    def first_free_serial(self):
        return Device.objects.aggregate(models.Max('pk'))['pk__max'] + 1

    def get_creation_dt_as_string(self):
        return get_dt_as_string(self.creation_dt)

    def latest_deviceevent_of_type(self, event_type):
        qs = self.deviceevent_set.filter(event_type=event_type)
        return qs.latest('event_dt') if qs.exists() else None

    def latest_deviceevent_description_of_type(self, event_type):
        dt = self.latest_deviceevent_of_type(event_type)
        return dt.description if dt else None

    def latest_sw_version(self):
        return self.latest_deviceevent_description_of_type('SW_VERSION')

    def latest_shipping(self):
        return self.latest_deviceevent_description_of_type('SHIPPING')


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
    image = models.ImageField(upload_to='test_images/')

    def __str__(self):
        return f'{self.test_record} - {self.image}'


def device_image_upload_path(instance, filename):
    """Generate upload path for device images: device_images/{device_id}/filename"""
    return f'device_images/{instance.device.id}/{filename}'


class DeviceImage(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    image_dt = models.DateTimeField(verbose_name='When', default=timezone.now)
    image = models.ImageField(upload_to=device_image_upload_path)
    notes = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ["device__id", "-image_dt"]

    def __str__(self):
        return f'{self.device}@{self.image_dt}: {self.image.name}'

    def get_image_dt_as_string(self):
        return get_dt_as_string(self.image_dt)


def design_asset_upload_path(instance, filename):
    return f'design_assets/{instance.design.id}/{filename}'


def device_asset_upload_path(instance, filename):
    return f'device_assets/{instance.device.id}/{filename}'


class DesignAsset(models.Model):
    FUSION = 'FUSION'
    PCB_DESIGN = 'PCB_DESIGN'
    SCHEMATIC = 'SCHEMATIC'
    BOM = 'BOM'
    PCB_TOP = 'PCB_TOP'
    PCB_BOTTOM = 'PCB_BOTTOM'
    PCB_3D = 'PCB_3D'
    FIRMWARE = 'FIRMWARE'
    ATTACHMENT = 'ATTACHMENT'

    CORE_ASSET_TYPES = frozenset({FUSION, PCB_DESIGN, SCHEMATIC, BOM, PCB_TOP, PCB_BOTTOM, PCB_3D, FIRMWARE})

    ASSET_TYPE_CHOICES = [
        ('Design Files', [
            (FUSION, 'Fusion Electronics Project'),
            (PCB_3D, 'PCB 3D View'),
            (PCB_TOP, 'PCB Top View'),
            (PCB_BOTTOM, 'PCB Bottom View'),
            (SCHEMATIC, 'Schematic Design File'),
            (PCB_DESIGN, 'PCB Design File'),
            (BOM, 'Bill of Materials'),
            (FIRMWARE, 'Firmware Binary'),
        ]),
        ('Additional', [
            (ATTACHMENT, 'Attachment'),
        ]),
    ]

    design = models.ForeignKey(Design, on_delete=models.CASCADE)
    file = models.FileField(upload_to=design_asset_upload_path)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    asset_type = models.CharField(max_length=20, choices=ASSET_TYPE_CHOICES, default=ATTACHMENT)
    uploaded_dt = models.DateTimeField(default=timezone.now)
    internal = models.BooleanField(default=False, help_text='Do not show this asset to clients')

    class Meta:
        ordering = ['asset_type', 'name']

    def __str__(self):
        return f'{self.design}: {self.name} ({self.get_asset_type_display()})'

    @property
    def is_core(self):
        return self.asset_type in self.CORE_ASSET_TYPES

    @property
    def filename(self):
        return os.path.basename(self.file.name)

    def get_icon_color(self):
        """Returns an inline color style value for this asset type, or empty string for default."""
        colors = {
            self.PCB_DESIGN: '#198754',
            self.SCHEMATIC:  "#b50d13",
        }
        return colors.get(self.asset_type, '')

    def get_icon_class(self):
        """Returns a Bootstrap Icons class for this asset type."""
        classes = {
            self.PCB_DESIGN: 'bi-cpu',
            self.SCHEMATIC: 'bi-diagram-3',
            self.BOM: 'bi-file-earmark-spreadsheet',
            self.PCB_TOP: 'bi-file-earmark-image',
            self.PCB_BOTTOM: 'bi-file-earmark-image',
            self.PCB_3D: 'bi-box',
            self.FIRMWARE: 'bi-file-earmark-binary',
            self.ATTACHMENT: 'bi-paperclip',
        }
        return classes.get(self.asset_type, 'bi-file-earmark')


class DeviceAsset(models.Model):
    ATTACHMENT = 'ATTACHMENT'

    CORE_ASSET_TYPES = frozenset()

    ASSET_TYPE_CHOICES = [
        (ATTACHMENT, 'Attachment'),
    ]

    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    file = models.FileField(upload_to=device_asset_upload_path)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    asset_type = models.CharField(max_length=20, choices=ASSET_TYPE_CHOICES, default=ATTACHMENT)
    uploaded_dt = models.DateTimeField(default=timezone.now)
    internal = models.BooleanField(default=False, help_text='Do not show this asset to clients')

    class Meta:
        ordering = ['asset_type', 'name']

    def __str__(self):
        return f'{self.device}: {self.name} ({self.get_asset_type_display()})'

    @property
    def is_core(self):
        return self.asset_type in self.CORE_ASSET_TYPES

    @property
    def filename(self):
        return os.path.basename(self.file.name)

    def get_icon_class(self):
        classes = {
            self.ATTACHMENT: 'bi-paperclip',
        }
        return classes.get(self.asset_type, 'bi-file-earmark')


class DeviceEvent(models.Model):
    NOTE = 'NOTE'
    SW_VERSION = 'SW_VERSION'
    SHIPPING = 'SHIPPING'

    TYPE_CHOICES = [
        (NOTE, 'NOTE'),
        (SW_VERSION, 'SW_VERSION'),
        (SHIPPING, 'SHIPPING'),
    ]

    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    event_dt = models.DateTimeField(verbose_name='When', default=timezone.now)
    event_type = models.CharField(max_length=50, choices=TYPE_CHOICES, default=NOTE)
    internal = models.BooleanField(default=False, help_text='Do not show this event to clients')
    description = models.TextField()

    class Meta:
        ordering = ["device__id", "event_dt"]

    def __str__(self):
        return f'{self.device}@{self.event_dt}: {self.description}'

    def get_event_dt_as_string(self):
        return get_dt_as_string(self.event_dt)

    def get_type_display(self):
        return {
            'NOTE': '📝 Note',
            'SW_VERSION': '🏷️ Firmware',
            'SHIPPING': '🚚 Shipping',
        }.get(self.event_type, '🤷 Unknown')
