from django.urls import path

from . import views

app_name = 'device'

urlpatterns = [
    path('', views.top, name='top'),
    path('action/', views.general_action, name='general_action'),
]
