# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django.urls import path

from . import views

app_name = 'erp'

urlpatterns = [
    path('', views.settings_index, name='settings_index'),
    path('production-stages/', views.production_stage_list, name='production_stage_list'),
    path('production-stages/<int:production_stage_id>/', views.production_stage_edit, name='production_stage_edit'),
    path('production-stages/<int:production_stage_id>/delete/', views.production_stage_delete, name='production_stage_delete'),
    path('production-stages/<int:production_stage_id>/move-<str:direction>/', views.production_stage_move, name='production_stage_move'),
    path('production-stage-templates/', views.production_stage_template_list, name='production_stage_template_list'),
    path('production-stage-templates/<int:template_id>/', views.production_stage_template_edit, name='production_stage_template_edit'),
    path('production-stage-templates/<int:template_id>/delete/', views.production_stage_template_delete, name='production_stage_template_delete'),
    path('production-stage-templates/<int:template_id>/add-step/', views.production_stage_template_step_add, name='production_stage_template_step_add'),
    path('production-stage-templates/step/<int:step_id>/delete/', views.production_stage_template_step_delete, name='production_stage_template_step_delete'),
    path('production-stage-templates/step/<int:step_id>/move-<str:direction>/', views.production_stage_template_step_move, name='production_stage_template_step_move'),
]
