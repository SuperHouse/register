"""Favicon (issue #151): the Testomatic icon, reachable without logging in."""

import pytest


@pytest.mark.django_db
def test_favicon_ico_redirects_to_static_without_login(client):
    response = client.get('/favicon.ico')
    # Temporary redirect, so a future icon change isn't hidden by a cached 301.
    assert response.status_code == 302
    assert response['Location'] == '/static/favicon.ico'


@pytest.mark.django_db
def test_login_page_links_icons(client):
    html = client.get('/accounts/login/', follow=True).content.decode()
    assert 'rel="icon"' in html
    assert 'rel="apple-touch-icon"' in html
