# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django.urls import path

from . import views

app_name = 'erp'

urlpatterns = [
    path('settings/', views.settings_index, name='settings_index'),
    path('settings/production-stages/', views.production_stage_list, name='production_stage_list'),
    path('settings/production-stages/<int:production_stage_id>/', views.production_stage_edit, name='production_stage_edit'),
    path('settings/production-stages/<int:production_stage_id>/delete/', views.production_stage_delete, name='production_stage_delete'),
    path('settings/production-stages/reorder/', views.production_stage_reorder, name='production_stage_reorder'),
    path('settings/locations/', views.location_list, name='location_list'),
    path('settings/locations/add/', views.location_add, name='location_add'),
    path('settings/locations/<int:location_id>/', views.location_edit, name='location_edit'),
    path('settings/locations/<int:location_id>/delete/', views.location_delete, name='location_delete'),
    path('settings/part-categories/', views.part_category_list, name='part_category_list'),
    path('settings/part-categories/add/', views.part_category_add, name='part_category_add'),
    path('settings/part-categories/<int:part_category_id>/', views.part_category_edit, name='part_category_edit'),
    path('settings/part-categories/<int:part_category_id>/delete/', views.part_category_delete, name='part_category_delete'),
    path('settings/production-stage-templates/', views.production_stage_template_list, name='production_stage_template_list'),
    path('settings/production-stage-templates/reorder/', views.production_stage_template_reorder, name='production_stage_template_reorder'),
    path('settings/production-stage-templates/<int:template_id>/', views.production_stage_template_edit, name='production_stage_template_edit'),
    path('settings/production-stage-templates/<int:template_id>/delete/', views.production_stage_template_delete, name='production_stage_template_delete'),
    path('settings/production-stage-templates/<int:template_id>/add-step/', views.production_stage_template_step_add, name='production_stage_template_step_add'),
    path('settings/production-stage-templates/step/<int:step_id>/delete/', views.production_stage_template_step_delete, name='production_stage_template_step_delete'),
    path('settings/production-stage-templates/<int:template_id>/reorder-steps/', views.production_stage_template_step_reorder, name='production_stage_template_step_reorder'),

    path('batches/', views.batch_list, name='batch_list'),
    path('batches/add/', views.batch_add, name='batch_add'),
    path('batches/<int:batch_id>/', views.batch_edit, name='batch_edit'),
    path('batches/<int:batch_id>/delete/', views.batch_delete, name='batch_delete'),
    path('batches/<int:batch_id>/apply-template/', views.batch_apply_template, name='batch_apply_template'),
    path('batches/<int:batch_id>/add-production-stage/', views.batch_production_stage_add, name='batch_production_stage_add'),
    path('batches/production-stage/<int:batch_production_stage_id>/update/', views.batch_production_stage_update, name='batch_production_stage_update'),
    path('batches/production-stage/<int:batch_production_stage_id>/set-status/<str:status>/', views.batch_production_stage_set_status, name='batch_production_stage_set_status'),
    path('batches/production-stage/<int:batch_production_stage_id>/delete/', views.batch_production_stage_delete, name='batch_production_stage_delete'),
    path('batches/<int:batch_id>/reorder-production-stages/', views.batch_production_stage_reorder, name='batch_production_stage_reorder'),
]
