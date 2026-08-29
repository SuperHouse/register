# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django.contrib import admin

from .models import ManualCheck, Tester, TestModule, TestModuleType, TestStep, TestSuite


@admin.register(Tester)
class TesterAdmin(admin.ModelAdmin):
    list_display = ['name', 'version']
    search_fields = ['name', 'notes']


class TestModuleInline(admin.TabularInline):
    model = TestModule
    extra = 0


@admin.register(TestModuleType)
class TestModuleTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'version']
    search_fields = ['name']
    filter_horizontal = ['compatible_designs']
    inlines = [TestModuleInline]


@admin.register(TestModule)
class TestModuleAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'module_type']
    list_select_related = ['module_type']
    search_fields = ['module_type__name', 'notes']


class TestStepInline(admin.TabularInline):
    model = TestStep
    extra = 0


class ManualCheckInline(admin.TabularInline):
    model = ManualCheck
    extra = 0


@admin.register(TestSuite)
class TestSuiteAdmin(admin.ModelAdmin):
    list_display = ['design', 'version', 'status', 'created_dt']
    list_select_related = ['design']
    search_fields = ['design__sku', 'design__name']
    inlines = [TestStepInline, ManualCheckInline]


@admin.register(TestStep)
class TestStepAdmin(admin.ModelAdmin):
    list_display = ['name', 'step_type', 'suite', 'order', 'abort_on_fail']
    list_select_related = ['suite']
    search_fields = ['name', 'suite__design__sku', 'suite__design__name']


@admin.register(ManualCheck)
class ManualCheckAdmin(admin.ModelAdmin):
    list_display = ['text', 'suite', 'order']
    list_select_related = ['suite']
    search_fields = ['text', 'suite__design__sku', 'suite__design__name']
