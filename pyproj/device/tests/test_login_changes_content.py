import pytest

from django.urls import reverse


# Helper: Pass through a client which does not have a logged-in user
@pytest.fixture
def stranger_client(client):
    return client


# Helper: Create a client with a logged-in user with no special permissions
@pytest.fixture
def logged_in_user_client(client, django_user_model):
    user = django_user_model.objects.create_user(email='user1@example.com', password='pass1')
    client.force_login(user)

    return client


# The 'device:perm_report' view returns different HTML content depending
# on whether the user is logged in, and whether the user is a staff member.


def test_content_for_strangers(stranger_client):
    response = stranger_client.get(reverse('device:perm_report'))
    assert response.status_code == 200
    assert b"You're not logged in" in response.content
    assert b"your full name is" not in response.content


def test_content_for_logged_in_user(logged_in_user_client):
    response = logged_in_user_client.get(reverse('device:perm_report'))
    assert response.status_code == 200
    assert b"You're not logged in" not in response.content
    assert b"your full name is" in response.content
    assert b"Staff-only actions" not in response.content


def test_content_for_staff(admin_client):
    response = admin_client.get(reverse('device:perm_report'))
    assert response.status_code == 200
    assert b"You're not logged in" not in response.content
    assert b"your full name is" in response.content
    assert b"Staff-only actions" in response.content
