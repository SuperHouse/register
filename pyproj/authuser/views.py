from django.shortcuts import render
from django.contrib.auth.views import (
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)


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
