# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django.db import models


class Operation(models.Model):
    """A type of operation that can be performed on a batch (e.g. 'PCBs stocked', 'Top SMT complete')."""
    name = models.CharField(max_length=100, unique=True)
    color = models.CharField(max_length=7, default='#6c757d', help_text='Used to highlight this operation in the UI')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class OperationTemplate(models.Model):
    """A reusable collection of operations that can be applied to a batch (e.g. 'Double-sided hi-rel load')."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class OperationTemplateStep(models.Model):
    """An operation at a particular position within an OperationTemplate."""
    template = models.ForeignKey(OperationTemplate, on_delete=models.CASCADE, related_name='steps')
    operation = models.ForeignKey(Operation, on_delete=models.PROTECT)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.template}: {self.order}. {self.operation}'
