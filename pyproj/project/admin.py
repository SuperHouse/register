# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django.contrib import admin

from .models import Project, ProjectLogEntry


class ProjectLogEntryInline(admin.StackedInline):
    model = ProjectLogEntry
    extra = 0
    fields = ('date', 'kind', 'body', 'client_visible', 'created_by_user', 'updated_dt')
    readonly_fields = ('created_by_user', 'updated_dt')


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'org', 'phase', 'status', 'start_date', 'target_date')
    list_filter = ('phase', 'status', 'org')
    search_fields = ('code', 'name', 'description', 'org__company_name')
    readonly_fields = ('code', 'created_dt')
    filter_horizontal = ('designs',)
    inlines = [ProjectLogEntryInline]
