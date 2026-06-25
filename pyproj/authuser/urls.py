from django.urls import include, path

from . import views

# Rewrite the password reset url handler with our own views that point to our templates
overrides = {
    'password_reset': views.SuperHousePasswordResetView,
    'password_reset_done': views.SuperHousePasswordResetDoneView,
    'password_reset_confirm': views.SuperHousePasswordResetConfirmView,
    'password_reset_complete': views.SuperHousePasswordResetCompleteView,
}

auth_patterns = path('', include('django.contrib.auth.urls'))
for i, pattern in enumerate(auth_patterns.url_patterns):
    if pattern.name in overrides:
        route = auth_patterns.url_patterns[i].pattern._route
        auth_patterns.url_patterns[i] = path(route, overrides[pattern.name].as_view(), name=pattern.name)

urlpatterns = [
    auth_patterns,
    path('settings/', views.user_settings, name='user_settings'),
    path('settings/regenerate-key/', views.user_settings_regenerate_key, name='user_settings_regenerate_key'),
]
