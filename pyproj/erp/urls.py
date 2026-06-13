# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django.urls import path

from . import views

app_name = 'erp'

urlpatterns = [
    path('', views.settings_index, name='settings_index'),
    path('operations/', views.operation_list, name='operation_list'),
    path('operations/<int:operation_id>/', views.operation_edit, name='operation_edit'),
    path('operations/<int:operation_id>/delete/', views.operation_delete, name='operation_delete'),
    path('templates/', views.template_list, name='template_list'),
    path('templates/<int:template_id>/', views.template_edit, name='template_edit'),
    path('templates/<int:template_id>/delete/', views.template_delete, name='template_delete'),
    path('templates/<int:template_id>/add-step/', views.template_step_add, name='template_step_add'),
    path('templates/step/<int:step_id>/delete/', views.template_step_delete, name='template_step_delete'),
    path('templates/step/<int:step_id>/move-<str:direction>/', views.template_step_move, name='template_step_move'),
]
