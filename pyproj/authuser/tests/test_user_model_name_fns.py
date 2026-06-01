import pytest


# FIXME: We may need to change this scope to 'module', 'class' or 'session'
# I don't yet understand the mechanics of this.
@pytest.fixture(scope='function')
def function_fixture(django_user_model):
    return django_user_model.objects.create(
        preferred_name='John',
        full_name='John Smith',
        email='johns@example.com',
    )


def test_shortname_prefers_preferred(client, function_fixture):
    user = function_fixture
    assert user.get_short_name() == 'John'


def test_shortname_finds_full_name(client, function_fixture):
    user = function_fixture
    user.preferred_name = ''

    assert user.get_short_name() == 'John Smith'


def test_shortname_finds_email(client, function_fixture):
    user = function_fixture
    user.preferred_name = ''
    user.full_name = ''

    assert user.get_short_name() == 'johns'


def test_shortname_fallback(client, function_fixture):
    user = function_fixture
    user.preferred_name = ''
    user.full_name = ''
    user.email = ''

    assert user.get_short_name() == ''
