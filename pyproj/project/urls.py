# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django.urls import path

from . import views

app_name = 'project'

urlpatterns = [
    path('projects/', views.project_list, name='project_list'),
    path('projects/add/', views.project_add, name='project_add'),
    path('projects/<int:project_id>/', views.project_detail, name='project_detail'),
    path('projects/<int:project_id>/edit/', views.project_edit, name='project_edit'),
    path('projects/<int:project_id>/link-design/', views.project_design_link, name='project_design_link'),
    path('projects/<int:project_id>/unlink-design/<int:design_id>/', views.project_design_unlink, name='project_design_unlink'),
    path('projects/<int:project_id>/log/add/', views.project_log_add, name='project_log_add'),
    path('projects/log/<int:entry_id>/edit/', views.project_log_edit, name='project_log_edit'),
    path('projects/log/<int:entry_id>/delete/', views.project_log_delete, name='project_log_delete'),
]
