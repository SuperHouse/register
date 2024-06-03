from django.urls import path

from . import views

app_name = 'device'

urlpatterns = [
    path('', views.top, name='top'),
    # Test code uses this, not for actual people to use, except for demos
    path('perm-report/', views.perm_report, name='perm_report'),
    path('action/', views.general_action, name='general_action'),
    # Permanent URLs
    path('add/', views.add_devices, name='add_devices'),
    path('<int:device_number>/', views.device_detail, name='device_detail'),
    path('<int:device_number>/action/', views.device_action, name='device_action'),
    path('event/<int:device_number>/de-add/', views.device_event_add, name='device_event_add'),
    path('event/<int:device_event_number>/de-edit/', views.device_event_edit, name='device_event_edit'),
    path('<int:device_event_number>/de-del/', views.device_event_delete, name='device_event_delete'),
    path('event/<int:test_record_number>/tr-edit/', views.test_record_edit, name='test_record_edit'),
]
