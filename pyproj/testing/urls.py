# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django.urls import path

from . import views

app_name = 'testing'

urlpatterns = [
    path('testers/', views.tester_list, name='tester_list'),
    path('testers/add/', views.tester_add, name='tester_add'),
    path('testers/<int:tester_id>/', views.tester_edit, name='tester_edit'),
    path('testers/<int:tester_id>/delete/', views.tester_delete, name='tester_delete'),
    path('testers/modules/add/', views.test_module_add, name='test_module_add'),
    path('testers/modules/<int:module_id>/', views.test_module_edit, name='test_module_edit'),
    path('testers/modules/<int:module_id>/delete/', views.test_module_delete, name='test_module_delete'),
    path('settings/test-module-types/', views.test_module_type_list, name='test_module_type_list'),
    path('testers/module-types/add/', views.test_module_type_add, name='test_module_type_add'),
    path('testers/module-types/<int:module_type_id>/', views.test_module_type_edit, name='test_module_type_edit'),
    path('testers/module-types/<int:module_type_id>/delete/', views.test_module_type_delete, name='test_module_type_delete'),
    path('testers/module-types/<int:module_type_id>/add-design/', views.test_module_type_design_add, name='test_module_type_design_add'),
    path('testers/module-types/<int:module_type_id>/remove-design/<int:design_id>/', views.test_module_type_design_remove, name='test_module_type_design_remove'),

    path('design/<int:design_id>/test-suite/copy-steps-from/', views.test_suite_copy_steps_from, name='test_suite_copy_steps_from'),
    path('design/<int:design_id>/test-suite/save-new-version/', views.test_suite_save_new_version, name='test_suite_save_new_version'),
    path('design/<int:design_id>/test-suite/versions/', views.test_suite_version_list, name='test_suite_version_list'),
    path('design/<int:design_id>/test-suite/versions/<int:version>/', views.test_suite_version_detail, name='test_suite_version_detail'),
    path('design/<int:design_id>/test-suite/steps/add/', views.test_step_add, name='test_step_add'),
    path('design/<int:design_id>/test-suite/steps/reorder/', views.test_step_reorder, name='test_step_reorder'),
    path('test-suites/steps/<int:step_id>/', views.test_step_edit, name='test_step_edit'),
    path('test-suites/steps/<int:step_id>/delete/', views.test_step_delete, name='test_step_delete'),
]
