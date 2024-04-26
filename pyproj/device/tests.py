import pytest

from django.urls import reverse


@pytest.mark.django_db
def test_view_top(client):
    response = client.get(reverse('device:top'))
    assert response.status_code == 200

    assert '<h1>SuperHouse Device Register</h1>' in response.content.decode('utf-8')


# Does the admin interface cause a redirect for a normal user?
@pytest.mark.django_db
def test_unauthorized(client):
    url = reverse('admin:index')
    response = client.get(url)
    assert response.status_code == 302


# Does the admin interface work ok for a superuser?
@pytest.mark.django_db
def test_superuser_view(admin_client):
    url = reverse('admin:index')
    response = admin_client.get(url)
    assert response.status_code == 200
