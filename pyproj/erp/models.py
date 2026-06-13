# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django.db import models


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
