# Useful page on testing with pytest: https://djangostars.com/blog/django-pytest-testing/

import re
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


# Note: If a user is not logged in, all page requests will give a 302 to the login page
# If a user is logged in but not a staff member, then all admin page requests will give a 302 to the login page


# Is the admin interface hidden from a stranger?
@pytest.mark.django_db
def test_admin_stranger_fails(stranger_client):
    url = reverse('admin:index')
    response = stranger_client.get(url)
    assert response.status_code == 302
    assert response['Location'] == reverse('login') + '?next=' + url


# Is the admin interface hidden from an ordinary user?
@pytest.mark.django_db
def test_admin_user_fails(logged_in_user_client):
    url = reverse('admin:index')
    response = logged_in_user_client.get(url)
    assert response.status_code == 302
    assert response['Location'] == reverse('admin:login') + '?next=' + url


# Does the admin interface 200 for a superuser?
@pytest.mark.django_db
def test_admin_superuser_ok(admin_client):
    url = reverse('admin:index')
    response = admin_client.get(url)
    assert response.status_code == 200


# Is a non-existent page in the admin interface hidden from a stranger?
@pytest.mark.django_db
def test_admin_missing_stranger_fails(stranger_client):
    url = reverse('admin:index') + 'not-there/'
    response = stranger_client.get(url)
    assert response.status_code == 302
    assert response['Location'] == reverse('login') + '?next=' + url


# Is a non-existent page in the admin interface hidden from an ordinary user?
@pytest.mark.django_db
def test_admin_missing_user_fails(logged_in_user_client):
    url = reverse('admin:index') + 'not-there/'
    response = logged_in_user_client.get(url)
    assert response.status_code == 302
    assert response['Location'] == reverse('admin:login') + '?next=' + url


# Does a non-existent page in the admin interface give a 404 for a superuser?
@pytest.mark.django_db
def test_admin_superuser_404(admin_client):
    url = reverse('admin:index') + 'not-there/'
    response = admin_client.get(url)
    assert response.status_code == 404


# Is the top level page hidden from a stranger?
@pytest.mark.django_db
def test_top_stranger_fails(stranger_client):
    url = reverse('device:top')
    response = stranger_client.get(url)
    assert response.status_code == 302
    assert response['Location'] == reverse('login') + '?next=' + url


# Does the top level page succeed for a simple user who is logged in?
@pytest.mark.django_db
def test_top_user_ok(logged_in_user_client):
    response = logged_in_user_client.get(reverse('device:top'))
    assert response.status_code == 200
    assert re.search(r'<h1>\s*SuperHouse Device Register\s*</h1>', response.content.decode('utf-8'), re.MULTILINE)


# Is a non-existent page hidden from a stranger? (ie, not 404)
@pytest.mark.django_db
def test_404_stranger_fails(stranger_client):
    url = reverse('device:top') + 'not-there/'
    response = stranger_client.get(url)
    assert response.status_code == 302
    assert response['Location'] == reverse('login') + '?next=' + url


# Does a non-existent page give a 404 to an ordinary user?
def test_404_user_ok(logged_in_user_client):
    url = reverse('device:top') + 'not-there/'
    response = logged_in_user_client.get(url)
    assert response.status_code == 404


# Does a non-existent page give a 404 to a superuser?
def test_404_superuser_ok(admin_client):
    url = reverse('device:top') + 'not-there/'
    response = admin_client.get(url)
    assert response.status_code == 404


# Does the general action view fail for a user who is not logged in?
@pytest.mark.django_db
def test_not_logged_in_fails(stranger_client):
    url = reverse('device:general_action')
    response = stranger_client.get(url)
    assert response.status_code == 302
    assert response['Location'] == reverse('login') + '?next=' + url


# Does the general action view succeed for a user who is logged in?
@pytest.mark.django_db
def test_logged_in_succeeds(logged_in_user_client):
    url = reverse('device:general_action')
    response = logged_in_user_client.get(url)
    assert response.status_code == 200
