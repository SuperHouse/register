from django.urls import path

from . import views

app_name = 'device'

urlpatterns = [
    path('', views.top, name='top'),
    path('action/', views.general_action, name='general_action'),
    path("<int:device_number>/", views.device_detail, name='device_detail'),
    path("<int:device_number>/action/", views.device_action, name='device_action'),
]
