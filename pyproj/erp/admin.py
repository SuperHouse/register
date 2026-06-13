# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django.contrib import admin

from .models import Operation, OperationTemplate, OperationTemplateStep


@admin.register(Operation)
class OperationAdmin(admin.ModelAdmin):
    list_display = ['name', 'color']
    search_fields = ['name']


class OperationTemplateStepInline(admin.TabularInline):
    model = OperationTemplateStep
    extra = 1


@admin.register(OperationTemplate)
class OperationTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']
    search_fields = ['name']
    inlines = [OperationTemplateStepInline]
