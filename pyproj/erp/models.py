# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django.db import models
from django.utils import timezone

from device.models import Design


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

    class Meta:
        ordering = ['name']

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
    completion_date = models.DateField(null=True, blank=True)

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
