from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = 'device'

urlpatterns = [
    path('', views.top, name='top'),  # Devices page at /device/
    path('dashboard/', RedirectView.as_view(url='/dashboard/', permanent=False), name='dashboard'),  # Redirect to root dashboard
    path('bootstrap-demo/', views.bootstrap_demo, name='bootstrap_demo'),
    # Test code uses this, not for actual people to use, except for demos
    path('perm-report/', views.perm_report, name='perm_report'),
    path('action/', views.general_action, name='general_action'),
    path('incdemo/', views.inc_demo, name='inc_demo'),
    path('messages/', views.test_messages, name='messages'),
    # Permanent URLs
    path('grid/', views.device_grid, name='device_grid'),
    path('search/', views.device_search, name='device_search'),
    path('<int:device_number>/', views.device_detail, name='device_detail'),
    path('<int:device_number>/action/', views.device_action, name='device_action'),
    path('<int:device_number>/de-add/', views.device_event_add, name='device_event_add'),
    path('de/<int:device_event_number>/', views.device_event_edit, name='device_event_edit'),
    path('de/<int:device_event_number>/delete/', views.device_event_delete, name='device_event_delete'),
    path('<int:device_number>/tr-add/', views.test_record_add, name='test_record_add'),
    path('tr/<int:test_record_number>/', views.test_record_edit, name='test_record_edit'),
    path('<int:device_number>/add-device-image/', views.device_image_add, name='device_image_add'),
    path('di/<int:device_image_number>/', views.device_image_edit, name='device_image_edit'),
    path('di/<int:device_image_number>/delete/', views.device_image_delete, name='device_image_delete'),
]
