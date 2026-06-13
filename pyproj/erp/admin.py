# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django.contrib import admin

from .models import ProductionStage, ProductionStageTemplate, ProductionStageTemplateStep


@admin.register(ProductionStage)
class ProductionStageAdmin(admin.ModelAdmin):
    list_display = ['name', 'color']
    search_fields = ['name']


class ProductionStageTemplateStepInline(admin.TabularInline):
    model = ProductionStageTemplateStep
    extra = 1


@admin.register(ProductionStageTemplate)
class ProductionStageTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']
    search_fields = ['name']
    inlines = [ProductionStageTemplateStepInline]
