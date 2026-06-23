from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from django.contrib.auth.views import (
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)

from .forms import UserSettingsForm


# /accounts/password_reset/	authuser.views.SuperHousePasswordResetView	password_reset
class SuperHousePasswordResetView(PasswordResetView):
    from_email = 'noreply@superhouse.tv'
    template_name = 'registration/superhouse_password_reset_form.html'
    email_template_name = 'registration/superhouse_password_reset_email.html'
    subject_template_name = 'registration/superhouse_password_reset_subject.txt'


# /accounts/password_reset/done/	django.contrib.auth.views.SuperHousePasswordResetDoneView	password_reset_done
class SuperHousePasswordResetDoneView(PasswordResetDoneView):
    template_name = "registration/superhouse_password_reset_done.html"


# /accounts/reset/<uidb64>/<token>/	django.contrib.auth.views.SuperHousePasswordResetConfirmView	password_reset_confirm
class SuperHousePasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "registration/superhouse_password_reset_confirm.html"


# /accounts/reset/done/	django.contrib.auth.views.SuperHousePasswordResetCompleteView	password_reset_complete
class SuperHousePasswordResetCompleteView(PasswordResetCompleteView):
    template_name = "registration/superhouse_password_reset_complete.html"


@login_required
def user_settings(request):
    if request.method == 'POST':
        form = UserSettingsForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your settings have been updated successfully.')
            return redirect('user_settings')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserSettingsForm(instance=request.user)
    
    return render(request, 'authuser/user_settings.html', {
        'form': form,
    })


@login_required
@require_POST
def user_settings_regenerate_key(request):
    request.user.regenerate_api_key()
    messages.success(request, 'Your API key has been regenerated.')

    return redirect('user_settings')
