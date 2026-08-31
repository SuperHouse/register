# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
import pytest

from device.tests.test_api import TestClientWithAuth

from authuser.api import router


@pytest.fixture
def calling_device(django_user_model):
    """The device itself authenticates with its own API key, same as every other endpoint on
    this router - it does not need to be staff itself, since it's only ever checking someone
    else's credentials, not acting as that user."""
    device_user = django_user_model.objects.create_user(email='device@example.com', password='irrelevant')
    device_user.api_key = 'api-key-for-calling-device'
    device_user.save()
    return device_user


@pytest.fixture
def staff_operator(django_user_model):
    user = django_user_model.objects.create_user(
        email='operator@example.com', password='correct-horse-battery-staple',
        full_name='Ops Erator', avatar_type='gravatar', is_staff=True,
    )
    return user


@pytest.fixture
def non_staff_operator(django_user_model):
    return django_user_model.objects.create_user(
        email='customer@example.com', password='customer-password', is_staff=False,
    )


def test_valid_staff_credentials_return_profile(calling_device, staff_operator):
    api_client = TestClientWithAuth(router, calling_device.api_key)
    response = api_client.post('verify_operator', json={
        'email': 'operator@example.com', 'password': 'correct-horse-battery-staple',
    })

    assert response.status_code == 200
    assert response.json() == {
        'id': staff_operator.pk,
        'email': 'operator@example.com',
        'full_name': 'Ops Erator',
        'avatar_type': 'gravatar',
        'is_staff': True,
    }


def test_wrong_password_returns_401(calling_device, staff_operator):
    api_client = TestClientWithAuth(router, calling_device.api_key)
    response = api_client.post('verify_operator', json={
        'email': 'operator@example.com', 'password': 'wrong-password',
    })

    assert response.status_code == 401


def test_unknown_email_returns_401(calling_device):
    api_client = TestClientWithAuth(router, calling_device.api_key)
    response = api_client.post('verify_operator', json={
        'email': 'nobody@example.com', 'password': 'whatever',
    })

    assert response.status_code == 401


def test_non_staff_credentials_return_403(calling_device, non_staff_operator):
    api_client = TestClientWithAuth(router, calling_device.api_key)
    response = api_client.post('verify_operator', json={
        'email': 'customer@example.com', 'password': 'customer-password',
    })

    assert response.status_code == 403


def test_requires_a_valid_device_api_key(staff_operator):
    api_client = TestClientWithAuth(router, 'not-a-real-api-key')
    response = api_client.post('verify_operator', json={
        'email': 'operator@example.com', 'password': 'correct-horse-battery-staple',
    })

    assert response.status_code == 401
