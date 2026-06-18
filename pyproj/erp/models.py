# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
import os

from django.db import models
from django.utils import timezone

from device.models import Design


def part_asset_upload_path(instance, filename):
    return f'part_assets/{instance.part_id}/{filename}'


class ProductionStage(models.Model):
    """A stage that a batch can pass through during production (e.g. 'PCBs stocked', 'Top SMT complete')."""
    name = models.CharField(max_length=100, unique=True)
    color = models.CharField(max_length=7, default='#6c757d', help_text='Used to highlight this production stage in the UI')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.name


class ProductionStageTemplate(models.Model):
    """A reusable collection of production stages that can be applied to a batch (e.g. 'Double-sided hi-rel load')."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class ProductionStageTemplateStep(models.Model):
    """A production stage at a particular position within a ProductionStageTemplate."""
    template = models.ForeignKey(ProductionStageTemplate, on_delete=models.CASCADE, related_name='steps')
    production_stage = models.ForeignKey(ProductionStage, on_delete=models.PROTECT)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.template}: {self.order}. {self.production_stage}'


class Batch(models.Model):
    """A production run of a Design, with an ordered list of production operations to perform."""
    design = models.ForeignKey(Design, on_delete=models.PROTECT, related_name='batches')
    reference = models.CharField(max_length=50, blank=True)
    quantity = models.PositiveIntegerField()
    notes = models.TextField(null=True, blank=True)
    created_dt = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_dt']

    def __str__(self):
        if self.reference:
            return f'{self.design} ({self.reference})'
        return f'{self.design} x{self.quantity}'


class Location(models.Model):
    """A physical location in a hierarchy (e.g. building > room > shelf)."""
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.CASCADE, related_name='children'
    )
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class Part(models.Model):
    """A component part that can be used in designs."""
    name = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    category = models.ForeignKey(
        'PartCategory', null=True, blank=True, on_delete=models.SET_NULL, related_name='parts'
    )
    device = models.CharField(max_length=200, blank=True, help_text='Component device or part identifier')
    package = models.CharField(max_length=100, blank=True, help_text='Package type (e.g. 0402, SOT-23)')
    value = models.CharField(max_length=100, blank=True, help_text='Component value (e.g. 10k, 100nF)')
    fusion_library = models.CharField(max_length=200, blank=True, help_text='Fusion Electronics library name')
    image = models.ImageField(upload_to='part_images/', null=True, blank=True)
    created_dt = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['name']

    def __str__(self):
        if self.value:
            return f'{self.name} ({self.value})'
        return self.name


class PartSource(models.Model):
    """A supplier or purchase source for a Part."""
    part = models.ForeignKey(Part, on_delete=models.CASCADE, related_name='sources')
    supplier_name = models.CharField(max_length=200)
    supplier_sku = models.CharField(max_length=200, blank=True)
    url = models.URLField(blank=True)
    manufacturer_sku = models.CharField(max_length=200, blank=True)
    packaging = models.CharField(max_length=100, blank=True)
    stock = models.PositiveIntegerField(null=True, blank=True, help_text='Leave blank if stock level is unknown')

    class Meta:
        ordering = ['supplier_name']

    def __str__(self):
        return f'{self.part}: {self.supplier_name}'


class PartAsset(models.Model):
    """A file attachment on a Part (e.g. datasheet)."""
    part = models.ForeignKey(Part, on_delete=models.CASCADE, related_name='assets')
    file = models.FileField(upload_to=part_asset_upload_path)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    uploaded_dt = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.part}: {self.name}'

    @property
    def filename(self):
        return os.path.basename(self.file.name)

    def get_icon_class(self):
        ext = os.path.splitext(self.file.name)[1].lower()
        icons = {
            '.pdf': 'bi-file-earmark-pdf',
            '.zip': 'bi-file-earmark-zip',
            '.xlsx': 'bi-file-earmark-spreadsheet',
            '.csv': 'bi-file-earmark-spreadsheet',
        }
        return icons.get(ext, 'bi-paperclip')


class PartCategory(models.Model):
    """A category in a hierarchy for classifying parts (e.g. Passives > Resistors > SMD)."""
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.CASCADE, related_name='children'
    )
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name_plural = 'part categories'

    def __str__(self):
        return self.name


class BomLibrarySetting(models.Model):
    """Per-Fusion-library behaviour applied when importing parts from a BOM CSV."""
    library = models.CharField(max_length=200, unique=True, help_text='Fusion Electronics library name')
    ignore_device = models.BooleanField(
        default=False,
        help_text="When importing parts from this library, ignore the 'device' field: it is not used to "
                   "detect duplicates and is not stored on the part.",
    )
    ignore_package = models.BooleanField(
        default=False,
        help_text="When importing parts from this library, ignore the 'package' field: it is not used to "
                   "detect duplicates and is not stored on the part.",
    )
    ignore_value = models.BooleanField(
        default=False,
        help_text="When importing parts from this library, ignore the 'value' field: it is not used to "
                   "detect duplicates and is not stored on the part.",
    )

    class Meta:
        ordering = ['library']

    def __str__(self):
        return self.library


class BomExclusionRule(models.Model):
    """A rule that causes matching rows in a BOM CSV import to be skipped entirely.

    Each of library/device/package/value may be left blank to match any value for that field;
    a row is excluded only if it matches every non-blank field on the rule.
    """
    library = models.CharField(max_length=200, blank=True, help_text='Leave blank to match any library')
    device = models.CharField(max_length=200, blank=True, help_text='Leave blank to match any device')
    package = models.CharField(max_length=100, blank=True, help_text='Leave blank to match any package')
    value = models.CharField(max_length=100, blank=True, help_text='Leave blank to match any value')

    class Meta:
        ordering = ['library', 'device', 'package', 'value']

    def __str__(self):
        parts = [
            f'library={self.library or "(any)"}',
            f'device={self.device or "(any)"}',
            f'package={self.package or "(any)"}',
            f'value={self.value or "(any)"}',
        ]
        return ', '.join(parts)


class BomEquivalenceRule(models.Model):
    """A rule that remaps a (device, package, value) triple to a different one during BOM import.

    library/from_device/from_package/from_value may be left blank to match any value for that field;
    a row matches only if it matches every non-blank "from" field on the rule.
    """
    library = models.CharField(max_length=200, blank=True, help_text='Leave blank to match any library')
    from_device = models.CharField(max_length=200, blank=True, help_text='Leave blank to match any device')
    to_device = models.CharField(max_length=200, blank=True, help_text='Leave blank to leave the device unchanged')
    from_package = models.CharField(max_length=100, blank=True, help_text='Leave blank to match any package')
    to_package = models.CharField(max_length=100, blank=True, help_text='Leave blank to leave the package unchanged')
    from_value = models.CharField(max_length=100, blank=True, help_text='Leave blank to match any value')
    to_value = models.CharField(max_length=100, blank=True, help_text='Leave blank to leave the value unchanged')

    class Meta:
        ordering = ['library', 'from_device', 'from_package', 'from_value']

    def __str__(self):
        from_parts = f'{self.from_device or "(any)"} {self.from_package or "(any)"} {self.from_value or "(any)"}'
        to_parts = (
            f'{self.to_device or self.from_device or "(any)"} '
            f'{self.to_package or self.from_package or "(any)"} '
            f'{self.to_value or self.from_value or "(any)"}'
        )
        return f'{from_parts} → {to_parts}'


class BatchProductionStage(models.Model):
    """A production stage on a Batch, snapshotted from a ProductionStage at the time it was added."""
    NOT_STARTED = 'NOT_STARTED'
    IN_PROGRESS = 'IN_PROGRESS'
    ON_HOLD = 'ON_HOLD'
    DONE = 'DONE'

    STATUS_CHOICES = [
        (NOT_STARTED, 'Not Started'),
        (IN_PROGRESS, 'In Progress'),
        (ON_HOLD, 'On Hold'),
        (DONE, 'Done'),
    ]

    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name='production_stages')
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=7, default='#6c757d')
    order = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=NOT_STARTED)
    due_date = models.DateField(null=True, blank=True)
    completion_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.batch}: {self.order}. {self.name}'

    def get_bootstrap_table_class(self):
        classes = {
            self.NOT_STARTED: '',
            self.IN_PROGRESS: 'table-info',
            self.ON_HOLD: 'table-warning',
            self.DONE: 'table-success',
        }

        return classes.get(self.status, '')
