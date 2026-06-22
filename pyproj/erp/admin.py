# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django.contrib import admin

from .models import (
    Batch, BatchProductionStage, BomEquivalenceRule, BomExclusionRule, BomLibrarySetting, Location, Part,
    PartAsset, PartCategory, PartSource, PartSourceVariant, ProductionStage, ProductionStageTemplate,
    ProductionStageTemplateStep,
)


class PartSourceVariantInline(admin.TabularInline):
    model = PartSourceVariant
    extra = 0


class PartSourceInline(admin.TabularInline):
    model = PartSource
    extra = 0


@admin.register(PartSource)
class PartSourceAdmin(admin.ModelAdmin):
    list_display = ['part', 'supplier_name', 'manufacturer_sku', 'stock']
    list_select_related = ['part']
    search_fields = ['part__name', 'supplier_name', 'manufacturer_sku']
    inlines = [PartSourceVariantInline]


class PartAssetInline(admin.TabularInline):
    model = PartAsset
    extra = 0
    readonly_fields = ['uploaded_dt']


@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'value', 'package', 'device', 'fusion_library']
    list_select_related = ['category']
    search_fields = ['name', 'description', 'device', 'package', 'value', 'fusion_library']
    inlines = [PartSourceInline, PartAssetInline]


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


@admin.register(BomLibrarySetting)
class BomLibrarySettingAdmin(admin.ModelAdmin):
    list_display = ['library', 'ignore_device', 'ignore_package', 'ignore_value']
    search_fields = ['library']


@admin.register(BomExclusionRule)
class BomExclusionRuleAdmin(admin.ModelAdmin):
    list_display = ['library', 'device', 'package']
    search_fields = ['library', 'device', 'package']


@admin.register(BomEquivalenceRule)
class BomEquivalenceRuleAdmin(admin.ModelAdmin):
    list_display = [
        'from_library', 'to_library', 'from_device', 'to_device',
        'from_package', 'to_package', 'from_value', 'to_value',
    ]
    search_fields = [
        'from_library', 'to_library', 'from_device', 'to_device',
        'from_package', 'to_package', 'from_value', 'to_value',
    ]
