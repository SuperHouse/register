# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django.contrib import admin

from .models import Batch, BatchProductionStage, Location, PartCategory, ProductionStage, ProductionStageTemplate, ProductionStageTemplateStep


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'description']
    list_select_related = ['parent']
    search_fields = ['name', 'description']


@admin.register(PartCategory)
class PartCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'description']
    list_select_related = ['parent']
    search_fields = ['name', 'description']


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


class BatchProductionStageInline(admin.TabularInline):
    model = BatchProductionStage
    extra = 0


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ['design', 'reference', 'quantity', 'created_dt']
    search_fields = ['reference', 'design__name', 'design__sku']
    inlines = [BatchProductionStageInline]
