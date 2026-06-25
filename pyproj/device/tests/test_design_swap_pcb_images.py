from unittest.mock import patch

from django.core.files.base import ContentFile
from django.urls import reverse
import pytest

from crm.models import Org
from device.models import Design, DesignAsset


@pytest.fixture
def design_with_top_and_bottom_assets():
    org = Org.objects.create(company_name='Swap Test Org')
    design = Design.objects.create(client=org, sku='SWAP1', name='Swap Test Design', hw_version='1.0')

    top_asset = DesignAsset(design=design, name='top', asset_type=DesignAsset.PCB_TOP)
    top_asset.file.save('swap-top.png', ContentFile(b'top-bytes'), save=True)

    bottom_asset = DesignAsset(design=design, name='bottom', asset_type=DesignAsset.PCB_BOTTOM)
    bottom_asset.file.save('swap-bottom.png', ContentFile(b'bottom-bytes'), save=True)

    return design, top_asset, bottom_asset


@pytest.mark.django_db
def test_swap_pcb_images_swaps_file_contents(client, django_user_model, design_with_top_and_bottom_assets):
    design, top_asset, bottom_asset = design_with_top_and_bottom_assets
    top_name = top_asset.file.name
    bottom_name = bottom_asset.file.name

    staff = django_user_model.objects.create_user(email='staff@example.com', password='staffy', is_staff=True)
    client.force_login(staff)

    response = client.post(reverse('design_swap_pcb_images', args=[design.pk]))
    assert response.status_code == 302

    top_asset.refresh_from_db()
    bottom_asset.refresh_from_db()

    # The rows still point at the same filenames/pks as before.
    assert top_asset.file.name == top_name
    assert bottom_asset.file.name == bottom_name

    # But the underlying file content has been swapped.
    assert top_asset.file.read() == b'bottom-bytes'
    bottom_asset.file.seek(0)
    assert bottom_asset.file.read() == b'top-bytes'


@pytest.mark.django_db
def test_swap_pcb_images_requires_staff(client, django_user_model, design_with_top_and_bottom_assets):
    design, top_asset, bottom_asset = design_with_top_and_bottom_assets

    user = django_user_model.objects.create_user(email='user@example.com', password='pass')
    client.force_login(user)

    response = client.post(reverse('design_swap_pcb_images', args=[design.pk]))
    assert response.status_code == 302
    assert response['Location'] != reverse('design_detail', args=[design.pk])

    top_asset.refresh_from_db()
    assert top_asset.file.read() == b'top-bytes'


@pytest.mark.django_db
def test_swap_pcb_images_survives_unowned_files(client, django_user_model, design_with_top_and_bottom_assets):
    """Files restored/extracted as another OS user can be renamed (needs only
    directory write access) but not have an explicit mtime set via os.utime
    (needs file ownership) - the swap should still succeed in that case."""
    design, top_asset, bottom_asset = design_with_top_and_bottom_assets

    staff = django_user_model.objects.create_user(email='staff3@example.com', password='staffy', is_staff=True)
    client.force_login(staff)

    with patch('device.views.os.utime', side_effect=PermissionError):
        response = client.post(reverse('design_swap_pcb_images', args=[design.pk]))
    assert response.status_code == 302

    top_asset.refresh_from_db()
    bottom_asset.refresh_from_db()
    assert top_asset.file.read() == b'bottom-bytes'
    bottom_asset.file.seek(0)
    assert bottom_asset.file.read() == b'top-bytes'


@pytest.mark.django_db
def test_swap_pcb_images_warns_when_one_missing(client, django_user_model):
    org = Org.objects.create(company_name='Swap Test Org 2')
    design = Design.objects.create(client=org, sku='SWAP2', name='Swap Test Design 2', hw_version='1.0')
    top_asset = DesignAsset(design=design, name='top', asset_type=DesignAsset.PCB_TOP)
    top_asset.file.save('swap-top2.png', ContentFile(b'top-bytes'), save=True)

    staff = django_user_model.objects.create_user(email='staff2@example.com', password='staffy', is_staff=True)
    client.force_login(staff)

    response = client.post(reverse('design_swap_pcb_images', args=[design.pk]))
    assert response.status_code == 302

    top_asset.refresh_from_db()
    assert top_asset.file.read() == b'top-bytes'
