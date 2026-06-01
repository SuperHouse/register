# from datetime import datetime

import pytest
from django.core import mail
from django.urls import reverse

from pytest_django.asserts import assertRedirects, assertTemplateUsed


## FIXME: This test is not complete.  It needs to test the email that is sent.
## https://github.com/SuperHouse/register/issues/5
## https://pytest-django.readthedocs.io/en/latest/helpers.html#mailoutbox


# # /accounts/password_reset/	authuser.views.SuperHousePasswordResetView	password_reset
def test_password_reset(client, db, mailoutbox):  # , create_users_and_user_data):
    # Test initial GET method
    response = client.get(reverse('password_reset'))
    assert response.status_code == 200

    should_use = (
        'device/base.html',
        'registration/superhouse_password_reset_form.html',
    )

    for template_name in should_use:
        assertTemplateUsed(response, template_name)

    # Now test the POST method.  This will send the email.
    data = {
        'email': 'user@example.com',
    }
    response = client.post(reverse('password_reset'), data, follow=True)
    assert response.status_code == 200
    assertRedirects(response, reverse('password_reset_done'))

    should_use = (
        'device/base.html',
        'registration/superhouse_password_reset_done.html',
    )

    for template_name in should_use:
        assertTemplateUsed(response, template_name)

    # m = mailoutbox
    # assert len(m) == 1

    # FIXME: Need to test these get used
    #     email_template_name = 'registration/superhouse_password_reset_email.html'
    #     subject_template_name = 'registration/superhouse_password_reset_subject.txt'

    # # /accounts/password_reset/done/	authuser.views.SuperHousePasswordResetDoneView	password_reset_done
    # # /accounts/reset/<uidb64>/<token>/	authuser.views.SuperHousePasswordResetConfirmView	password_reset_confirm
    # # /accounts/reset/done/	authuser.views.SuperHousePasswordResetCompleteView	password_reset_complete
