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
    notes = models.TextField(null=True, blank=True)
    created_dt = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['name']

    def __str__(self):
        if self.value:
            return f'{self.name} ({self.value})'
        return self.name


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
