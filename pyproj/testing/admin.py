# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django.contrib import admin

from .models import Tester, TestModule, TestModuleType


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
