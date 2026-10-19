"""Access rules for uploaded media files (conf/media.py)."""

import io

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.urls import reverse
from easy_thumbnails.files import get_thumbnailer
from PIL import Image
import pytest

from crm.models import Org
from device.models import Design, DesignAsset, Device, DeviceAsset, DeviceImage, TestRecord
from device.models import TestImage as TestImageModel  # aliased so pytest does not collect it as a test class


def png_bytes():
    buffer = io.BytesIO()
    Image.new('RGB', (40, 30), 'red').save(buffer, format='PNG')
    return buffer.getvalue()


def make_org_files(label, user):
    """One org, owned by `user`, with one file of every org-scoped kind. Returns {kind: stored name}."""
    org = Org.objects.create(company_name=f'Org {label}')
    org.users.add(user)
    org.logo.save(f'logo-{label}.png', ContentFile(png_bytes()), save=True)
    design = Design.objects.create(client=org, sku=f'SKU{label}', name=f'Design {label}', hw_version='1.0')
    device = Device.objects.create(design=design)
    test_record = TestRecord.objects.create(device=device)

    def design_asset(filename, content, internal=False):
        asset = DesignAsset(design=design, name=filename, asset_type=DesignAsset.ATTACHMENT, internal=internal)
        asset.file.save(filename, ContentFile(content), save=True)
        return asset.file.name

    device_asset = DeviceAsset(device=device, name='notes', asset_type=DeviceAsset.ATTACHMENT)
    device_asset.file.save(f'notes-{label}.txt', ContentFile(b'notes'), save=True)
    internal_device_asset = DeviceAsset(device=device, name='secret', asset_type=DeviceAsset.ATTACHMENT, internal=True)
    internal_device_asset.file.save(f'secret-{label}.txt', ContentFile(b'secret'), save=True)
    device_image = DeviceImage(device=device)
    device_image.image.save(f'board-{label}.png', ContentFile(png_bytes()), save=True)
    test_image = TestImageModel(test_record=test_record)
    test_image.image.save(f'test-{label}.png', ContentFile(png_bytes()), save=True)

    return {
        'logo': org.logo.name,
        'design_asset': design_asset(f'top-{label}.png', png_bytes()),
        'internal_design_asset': design_asset(f'internal-{label}.png', png_bytes(), internal=True),
        'svg_design_asset': design_asset(f'drawing-{label}.svg', b'<svg xmlns="http://www.w3.org/2000/svg"/>'),
        'pdf_design_asset': design_asset(f'datasheet-{label}.pdf', b'%PDF-1.4'),
        'device_asset': device_asset.file.name,
        'internal_device_asset': internal_device_asset.file.name,
        'device_image': device_image.image.name,
        'test_image': test_image.image.name,
        'thumbnail': get_thumbnailer(test_image.image)['testimage-thumbs'].name,
    }


@pytest.fixture
def media(settings, tmp_path, django_user_model):
    settings.MEDIA_ROOT = str(tmp_path)
    users = {
        'staff': django_user_model.objects.create_user(email='staff@example.com', password='x', is_staff=True),
        'member_a': django_user_model.objects.create_user(email='a@example.com', password='x'),
        'member_b': django_user_model.objects.create_user(email='b@example.com', password='x'),
    }
    files = {
        'a': make_org_files('A', users['member_a']),
        'b': make_org_files('B', users['member_b']),
        'staff_only': {
            prefix: default_storage.save(f'{prefix}/1/file.bin', ContentFile(b'data'))
            for prefix in ('part_images', 'part_assets', 'test_step_assets', 'test_step_diagnostic_images', 'other')
        },
    }
    return users, files


def get(client, name):
    return client.get(reverse('media', args=[name]))


@pytest.mark.django_db
def test_thumbnail_is_stored_under_thumbnail_basedir(media):
    _, files = media
    assert files['a']['thumbnail'].startswith('thumbs/test_images/')


@pytest.mark.django_db
def test_anonymous_is_sent_to_login(client, media):
    _, files = media
    url = reverse('media', args=[files['a']['design_asset']])
    response = client.get(url)
    assert response.status_code == 302
    assert response['Location'] == reverse('login') + '?next=' + url


@pytest.mark.django_db
def test_staff_can_get_every_file(client, media):
    users, files = media
    client.force_login(users['staff'])
    for group in files.values():
        for name in group.values():
            assert get(client, name).status_code == 200, name


@pytest.mark.django_db
def test_member_gets_own_orgs_files(client, media):
    users, files = media
    client.force_login(users['member_a'])
    for kind in ('logo', 'design_asset', 'svg_design_asset', 'pdf_design_asset', 'device_asset',
                 'device_image', 'test_image', 'thumbnail'):
        response = get(client, files['a'][kind])
        assert response.status_code == 200, kind
        assert response['Cache-Control'] == 'private'


@pytest.mark.django_db
def test_member_cannot_get_internal_assets(client, media):
    users, files = media
    client.force_login(users['member_a'])
    assert get(client, files['a']['internal_design_asset']).status_code == 404
    assert get(client, files['a']['internal_device_asset']).status_code == 404


@pytest.mark.django_db
def test_member_cannot_get_another_orgs_files(client, media):
    users, files = media
    client.force_login(users['member_a'])
    for kind, name in files['b'].items():
        assert get(client, name).status_code == 404, kind


@pytest.mark.django_db
def test_member_cannot_get_staff_only_files(client, media):
    users, files = media
    client.force_login(users['member_a'])
    for prefix, name in files['staff_only'].items():
        assert get(client, name).status_code == 404, prefix


@pytest.mark.django_db
def test_user_with_no_org_gets_nothing(client, media, django_user_model):
    _, files = media
    client.force_login(django_user_model.objects.create_user(email='nobody@example.com', password='x'))
    for name in files['a'].values():
        assert get(client, name).status_code == 404, name


@pytest.mark.django_db
@pytest.mark.parametrize('path', ['/media/../conf/settings.py', '/media/%2e%2e/conf/settings.py', '/media//etc/passwd'])
def test_paths_outside_media_root_are_refused(client, media, path):
    users, _ = media
    client.force_login(users['staff'])
    assert client.get(path).status_code == 404


@pytest.mark.django_db
def test_missing_file_is_404(client, media):
    users, files = media
    default_storage.delete(files['a']['design_asset'])
    client.force_login(users['staff'])
    assert get(client, files['a']['design_asset']).status_code == 404


@pytest.mark.django_db
def test_directory_is_404(client, media):
    users, _ = media
    client.force_login(users['staff'])
    assert get(client, 'design_assets').status_code == 404


@pytest.mark.django_db
def test_images_and_pdfs_are_inline_and_other_files_are_downloads(client, media):
    users, files = media
    client.force_login(users['member_a'])
    assert get(client, files['a']['design_asset'])['Content-Disposition'].startswith('inline')
    assert get(client, files['a']['pdf_design_asset'])['Content-Disposition'].startswith('inline')
    assert get(client, files['a']['svg_design_asset'])['Content-Disposition'].startswith('attachment')
    assert get(client, files['a']['device_asset'])['Content-Disposition'].startswith('attachment')


@pytest.mark.django_db
def test_unchanged_file_gives_304(client, media):
    users, files = media
    client.force_login(users['member_a'])
    first = get(client, files['a']['design_asset'])
    response = client.get(reverse('media', args=[files['a']['design_asset']]),
                          HTTP_IF_MODIFIED_SINCE=first['Last-Modified'])
    assert response.status_code == 304


@pytest.mark.django_db
def test_forbidden_file_gives_404_even_with_if_modified_since(client, media):
    users, files = media
    client.force_login(users['member_a'])
    response = client.get(reverse('media', args=[files['b']['design_asset']]),
                          HTTP_IF_MODIFIED_SINCE='Wed, 01 Jan 2099 00:00:00 GMT')
    assert response.status_code == 404
