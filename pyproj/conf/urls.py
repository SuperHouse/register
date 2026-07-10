"""
URL configuration.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.contrib import admin
from django.templatetags.static import static
from django.urls import include, path, re_path
from django.views.generic.base import RedirectView
from django.views.static import serve

from api.app import api
from device import api as device_api  # noqa: F401 — registers device endpoints on the shared router
from crm.views import api as crm_api  # noqa: F401 — registers crm endpoints on the shared router
from crm import views as crm_views
from device import views as device_views

urlpatterns = [
    path('', device_views.dashboard, name='home'),
    path('dashboard/', device_views.dashboard, name='dashboard'),

    path('design/', device_views.design_list, name='design_list'),
    path('design/<int:design_id>/', device_views.design_detail, name='design_detail'),
    path('design/<int:design_id>/add-asset/', device_views.design_asset_add, name='design_asset_add'),
    path('design/da/<int:asset_id>/', device_views.design_asset_edit, name='design_asset_edit'),
    path('design/da/<int:asset_id>/delete/', device_views.design_asset_delete, name='design_asset_delete'),
    path('design/<int:design_id>/swap-pcb-images/', device_views.design_swap_pcb_images, name='design_swap_pcb_images'),
    path('design/<int:design_id>/toggle-obsolete/', device_views.design_toggle_obsolete, name='design_toggle_obsolete'),
    path('design/<int:design_id>/update/', device_views.design_update, name='design_update'),
    path('organisation/', crm_views.organisation_list, name='organisation_list'),
    path('organisation/<int:client_id>/', crm_views.organisation_detail, name='organisation_detail'),
    path('organisation/<int:client_id>/edit/', crm_views.organisation_edit, name='organisation_edit'),
    path('users/', crm_views.user_list, name='user_list'),
    path('users/add/', crm_views.user_add, name='user_add'),
    path('users/<int:user_id>/', crm_views.user_edit, name='user_edit'),
    path('users/<int:user_id>/regenerate-key/', crm_views.user_regenerate_key, name='user_regenerate_key'),
    path('', include('erp.urls')),
    path('', include('testing.urls')),
    path('office/', admin.site.urls),
    path('accounts/', include('authuser.urls')),
    path('favicon.ico', RedirectView.as_view(url=static('favicon.ico'), permanent=True)),
    path('hijack/', include('hijack.urls')),
    path('device/', include('device.urls')),
    path('api/v1/', api.urls),

    # If we're running behind a web server, we won't see media requests, so this will do nothing.
    re_path(
        r'^media/(?P<path>.*)$',
        serve,
        {
            "document_root": settings.MEDIA_ROOT,
        },
    ),
]

if settings.DEBUG:
    urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]
