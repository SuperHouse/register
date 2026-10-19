"""Per-hostname branding (issue #150): crm.branding, the BrandedHost UI, and where branding shows up."""

import io

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.urls import reverse
from PIL import Image
import pytest

from crm.branding import accent_style, contrast_ratio, hex_to_rgb, needs_dark_text, sidebar_style
from crm.models import BrandedHost, Org
from device.models import Design
from erp.models import Batch

VANITY = 'serials.example.com'


def png_bytes(colour='blue'):
    buffer = io.BytesIO()
    Image.new('RGB', (20, 10), colour).save(buffer, format='PNG')
    return buffer.getvalue()


@pytest.fixture
def org(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    settings.ALLOWED_HOSTS = ['testserver', 'portal.superhouse.tv', VANITY]
    return Org.objects.create(company_name='Example Co')


@pytest.fixture
def branded_host(org):
    host = BrandedHost(org=org, hostname=VANITY, display_name='Example Serials',
                       logo_link_url='https://www.example.com/', sidebar_colour='#FFEE00', accent_colour='#123456')
    host.logo.save('example.png', ContentFile(png_bytes()), save=True)
    return host


@pytest.fixture
def staff(django_user_model):
    return django_user_model.objects.create_user(email='staff@example.com', password='x', is_staff=True)


# --- Colour helpers ---

def test_dark_text_on_light_background_and_light_text_on_dark():
    assert needs_dark_text(hex_to_rgb('#ffee00'))
    assert not needs_dark_text(hex_to_rgb('#3c4b64'))


def test_sidebar_style():
    assert sidebar_style('#ffee00') == {'colour': '#ffee00', 'dark_text': True}


def test_accent_link_colour_is_readable_on_white_even_for_a_light_accent():
    style = accent_style('#ffee00')
    assert contrast_ratio(hex_to_rgb(style['link']), (255, 255, 255)) >= 4.5
    assert style['text'].startswith('rgba(0, 0, 21')  # dark text on yellow buttons


def test_dark_accent_keeps_its_own_colour_for_links():
    style = accent_style('#123456')
    assert style['link'] == '#123456'
    assert style['text'].startswith('rgba(255, 255, 255')


# --- Model ---

@pytest.mark.django_db
def test_hostname_and_colours_are_stored_lowercase(org):
    host = BrandedHost(org=org, hostname='  Serials.Example.COM ', sidebar_colour='#ABCDEF')
    host.logo.save('x.png', ContentFile(png_bytes()), save=True)
    host.refresh_from_db()
    assert host.hostname == VANITY
    assert host.sidebar_colour == '#abcdef'


@pytest.mark.django_db
def test_brand_name_defaults_to_company_name(org):
    assert BrandedHost(org=org, hostname=VANITY).brand_name == 'Example Co'


# --- What pages show ---

@pytest.mark.django_db
def test_login_page_on_vanity_host_shows_brand_to_anonymous_visitor(client, branded_host):
    response = client.get(reverse('login'), HTTP_HOST=VANITY)
    content = response.content.decode()
    assert response.status_code == 200
    assert branded_host.logo.url in content
    assert 'href="https://www.example.com/"' in content
    assert 'Example Serials Device Register' in content
    assert '--cui-sidebar-bg: #ffee00' in content
    assert '--cui-primary: #123456' in content
    assert 'superhouse.png' not in content


@pytest.mark.django_db
def test_other_hostnames_get_superhouse_defaults(client, branded_host):
    content = client.get(reverse('login'), HTTP_HOST='portal.superhouse.tv').content.decode()
    assert 'superhouse.png' in content
    assert 'SuperHouse Device Register' in content
    assert '--cui-sidebar-bg' not in content
    assert branded_host.logo.url not in content


@pytest.mark.django_db
def test_hostname_match_ignores_port_and_case(client, branded_host, settings):
    settings.ALLOWED_HOSTS = ['.example.com']
    content = client.get(reverse('login'), HTTP_HOST='SERIALS.example.com:443').content.decode()
    assert branded_host.logo.url in content


@pytest.mark.django_db
def test_no_colours_means_no_style_block(client, branded_host):
    branded_host.sidebar_colour = branded_host.accent_colour = ''
    branded_host.save()
    content = client.get(reverse('login'), HTTP_HOST=VANITY).content.decode()
    assert '--cui-sidebar-bg' not in content
    assert '--cui-primary' not in content
    assert branded_host.logo.url in content


@pytest.mark.django_db
def test_blank_logo_link_goes_to_dashboard_in_same_tab(client, branded_host):
    branded_host.logo_link_url = ''
    branded_host.save()
    content = client.get(reverse('login'), HTTP_HOST=VANITY).content.decode()
    assert '<a class="sidebar-brand-full" href="/">' in content


@pytest.mark.django_db
def test_batch_print_page_uses_brand_logo(client, branded_host, staff):
    design = Design.objects.create(client=branded_host.org, sku='S1', name='Board', hw_version='1')
    batch = Batch.objects.create(design=design, quantity=1)
    client.force_login(staff)
    content = client.get(reverse('erp:batch_print', args=[batch.pk]), HTTP_HOST=VANITY).content.decode()
    assert branded_host.logo.url in content
    assert 'superhouse.png' not in content


# --- Branding logos are public; nothing else in branding/ is ---

@pytest.mark.django_db
def test_branding_logo_is_public(client, branded_host):
    response = client.get(reverse('media', args=[branded_host.logo.name]))
    assert response.status_code == 200


@pytest.mark.django_db
def test_other_files_in_branding_folder_are_not_public(client, org, staff):
    name = default_storage.save('branding/stray.png', ContentFile(png_bytes()))
    assert client.get(reverse('media', args=[name])).status_code == 404


# --- Password reset ---

@pytest.mark.django_db
def test_password_reset_email_uses_vanity_host_and_brand(client, branded_host, django_user_model, mailoutbox):
    django_user_model.objects.create_user(email='person@example.com', password='x')
    client.post(reverse('password_reset'), {'email': 'person@example.com'}, HTTP_HOST=VANITY)
    assert len(mailoutbox) == 1
    message = mailoutbox[0]
    assert message.subject == 'Password reset for Example Serials'
    assert f'://{VANITY}/accounts/reset/' in message.body
    assert 'portal.superhouse.tv' not in message.body


@pytest.mark.django_db
def test_password_reset_email_elsewhere_keeps_superhouse(client, org, django_user_model, mailoutbox):
    django_user_model.objects.create_user(email='person@example.com', password='x')
    client.post(reverse('password_reset'), {'email': 'person@example.com'}, HTTP_HOST='portal.superhouse.tv')
    message = mailoutbox[0]
    assert message.subject == 'Password reset for SuperHouse'
    assert '://portal.superhouse.tv/accounts/reset/' in message.body


@pytest.mark.django_db
def test_invite_email_uses_host_staff_is_on(client, branded_host, staff, mailoutbox):
    client.force_login(staff)
    client.post(reverse('user_add'), {'email': 'new@example.com', 'full_name': 'New', 'is_active': 'on'},
                HTTP_HOST=VANITY)
    assert len(mailoutbox) == 1
    assert f'://{VANITY}/accounts/reset/' in mailoutbox[0].body


# --- Staff UI on the organisation edit page ---

@pytest.mark.django_db
def test_add_branded_host(client, org, staff):
    client.force_login(staff)
    response = client.post(reverse('branded_host_add', args=[org.pk]), {
        'hostname': 'Brand.Example.com',
        'display_name': 'Brand',
        'logo': ContentFile(png_bytes(), name='brand.png'),
        'sidebar_colour': '#AABBCC',
        'accent_colour': '',
    })
    assert response.status_code == 302
    host = BrandedHost.objects.get()
    assert host.org == org
    assert host.hostname == 'brand.example.com'
    assert host.sidebar_colour == '#aabbcc'
    assert host.logo.name.startswith('branding/')


@pytest.mark.django_db
@pytest.mark.parametrize('hostname', ['https://brand.example.com', 'brand.example.com:8000', 'brand', 'brand.example.com/x'])
def test_add_branded_host_rejects_bad_hostnames(client, org, staff, hostname):
    client.force_login(staff)
    response = client.post(reverse('branded_host_add', args=[org.pk]), {
        'hostname': hostname, 'logo': ContentFile(png_bytes(), name='brand.png'),
    })
    assert response.status_code == 200
    assert not BrandedHost.objects.exists()


@pytest.mark.django_db
def test_add_branded_host_rejects_bad_colour(client, org, staff):
    client.force_login(staff)
    response = client.post(reverse('branded_host_add', args=[org.pk]), {
        'hostname': VANITY, 'logo': ContentFile(png_bytes(), name='brand.png'), 'accent_colour': 'red',
    })
    assert response.status_code == 200
    assert not BrandedHost.objects.exists()


@pytest.mark.django_db
def test_hostname_must_be_unique(client, branded_host, staff):
    client.force_login(staff)
    response = client.post(reverse('branded_host_add', args=[branded_host.org.pk]), {
        'hostname': VANITY.upper(), 'logo': ContentFile(png_bytes(), name='brand.png'),
    })
    assert response.status_code == 200
    assert BrandedHost.objects.count() == 1


@pytest.mark.django_db
def test_replacing_logo_deletes_old_file(client, branded_host, staff):
    old_name = branded_host.logo.name
    client.force_login(staff)
    response = client.post(reverse('branded_host_edit', args=[branded_host.pk]), {
        'hostname': VANITY, 'display_name': 'New', 'logo': ContentFile(png_bytes('green'), name='new.png'),
    })
    assert response.status_code == 302
    branded_host.refresh_from_db()
    assert branded_host.display_name == 'New'
    assert branded_host.logo.name != old_name
    assert not default_storage.exists(old_name)


@pytest.mark.django_db
def test_edit_without_new_logo_keeps_logo(client, branded_host, staff):
    old_name = branded_host.logo.name
    client.force_login(staff)
    client.post(reverse('branded_host_edit', args=[branded_host.pk]), {'hostname': VANITY, 'display_name': 'New'})
    branded_host.refresh_from_db()
    assert branded_host.logo.name == old_name
    assert default_storage.exists(old_name)


@pytest.mark.django_db
def test_delete_branded_host_removes_logo(client, branded_host, staff):
    name = branded_host.logo.name
    client.force_login(staff)
    assert client.post(reverse('branded_host_delete', args=[branded_host.pk])).status_code == 302
    assert not BrandedHost.objects.exists()
    assert not default_storage.exists(name)


@pytest.mark.django_db
def test_org_edit_page_lists_hosts_and_flags_missing_allowed_hosts(client, branded_host, staff, settings):
    client.force_login(staff)
    content = client.get(reverse('organisation_edit', args=[branded_host.org.pk])).content.decode()
    assert VANITY in content
    assert 'Not in ALLOWED_HOSTS' not in content

    settings.ALLOWED_HOSTS = ['testserver']
    content = client.get(reverse('organisation_edit', args=[branded_host.org.pk])).content.decode()
    assert 'Not in ALLOWED_HOSTS' in content


@pytest.mark.django_db
def test_branding_views_are_staff_only(client, branded_host, django_user_model):
    member = django_user_model.objects.create_user(email='member@example.com', password='x')
    branded_host.org.users.add(member)
    client.force_login(member)
    for url in (reverse('branded_host_add', args=[branded_host.org.pk]),
                reverse('branded_host_edit', args=[branded_host.pk])):
        assert client.get(url).status_code == 302
    assert client.post(reverse('branded_host_delete', args=[branded_host.pk])).status_code == 302
    assert BrandedHost.objects.exists()
