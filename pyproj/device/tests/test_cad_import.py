from unittest.mock import patch

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
import pytest

from crm.models import Org
from device import cad_import
from device.cad_import import (
    CadExtractor, CadImportError, ExtractedAssets, FusionCadExtractor, extractor_for_filename,
)
from device.models import Design, DesignAsset


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / 'media'


@pytest.fixture
def design():
    org = Org.objects.create(company_name='CAD Import Test Org')
    return Design.objects.create(client=org, sku='CAD1', name='CAD Import Test Design', hw_version='1.0')


@pytest.fixture
def staff_client(client, django_user_model):
    staff = django_user_model.objects.create_user(email='staff@example.com', password='staffy', is_staff=True)
    client.force_login(staff)
    return client


def _upload(client, design, filename, asset_type=DesignAsset.CAD_PROJECT):
    return client.post(
        reverse('design_asset_add', args=[design.pk]),
        {
            'file': SimpleUploadedFile(filename, b'project-bytes'),
            'name': 'upload',
            'asset_type': asset_type,
        },
        follow=True,
    )


def _fake_extract(project_path, out_dir):
    """Stands in for FusionCadExtractor.extract: writes a BOM, board, and top render."""
    bom = out_dir / 'whatever_bom.csv'
    bom.write_bytes(b'reference,device\n')
    board = out_dir / 'whatever.brd'
    board.write_bytes(b'<eagle/>')
    top = out_dir / 'whatever_pcb_3d_top.png'
    top.write_bytes(b'png')
    return ExtractedAssets(bom=bom, pcb_design=board, pcb_top=top)


def test_extractor_for_filename():
    assert isinstance(extractor_for_filename('board.f3z'), FusionCadExtractor)
    assert isinstance(extractor_for_filename('BOARD.F3Z'), FusionCadExtractor)
    assert extractor_for_filename('board.zip') is None
    assert extractor_for_filename('board') is None


def test_fusion_extractor_wraps_fusionextractor_errors(tmp_path):
    bad = tmp_path / 'bad.f3z'
    bad.write_bytes(b'not a zip')
    with pytest.raises(CadImportError):
        FusionCadExtractor().extract(bad, tmp_path)


@pytest.mark.django_db
def test_f3z_upload_extracts_assets_and_sets_cad_tool(staff_client, design):
    old_bom = DesignAsset(design=design, name='old', asset_type=DesignAsset.BOM)
    old_bom.file.save('old_bom.csv', ContentFile(b'old'), save=True)

    with patch.object(FusionCadExtractor, 'extract', side_effect=_fake_extract):
        response = _upload(staff_client, design, 'MyBoard.f3z')

    design.refresh_from_db()
    assert design.cad_tool == Design.CAD_FUSION

    assets = {a.asset_type: a for a in design.designasset_set.all()}
    assert set(assets) == {DesignAsset.CAD_PROJECT, DesignAsset.BOM, DesignAsset.PCB_DESIGN, DesignAsset.PCB_TOP}
    assert assets[DesignAsset.BOM].pk != old_bom.pk
    assert assets[DesignAsset.BOM].filename == 'MyBoard.csv'
    assert assets[DesignAsset.PCB_DESIGN].filename == 'MyBoard.brd'
    assert assets[DesignAsset.PCB_TOP].filename == 'MyBoard-top.png'

    text = response.content.decode()
    assert 'Extracted from Fusion Electronics Project: Bill of Materials, PCB Design File, PCB Top View.' in text


@pytest.mark.django_db
def test_failed_extraction_keeps_project_file_and_existing_assets(staff_client, design):
    old_bom = DesignAsset(design=design, name='old', asset_type=DesignAsset.BOM)
    old_bom.file.save('old_bom.csv', ContentFile(b'old'), save=True)

    with patch.object(FusionCadExtractor, 'extract', side_effect=CadImportError('broken archive')):
        response = _upload(staff_client, design, 'MyBoard.f3z')

    types = set(design.designasset_set.values_list('asset_type', flat=True))
    assert types == {DesignAsset.CAD_PROJECT, DesignAsset.BOM}
    assert DesignAsset.objects.filter(pk=old_bom.pk).exists()
    assert 'asset extraction failed: broken archive' in response.content.decode()


@pytest.mark.django_db
def test_unrecognised_project_file_is_stored_without_extraction(staff_client, design):
    with patch.object(FusionCadExtractor, 'extract') as extract:
        _upload(staff_client, design, 'notes.pdf')

    extract.assert_not_called()
    design.refresh_from_db()
    assert design.cad_tool == ''
    assert list(design.designasset_set.values_list('asset_type', flat=True)) == [DesignAsset.CAD_PROJECT]


@pytest.mark.django_db
def test_f3z_uploaded_as_attachment_is_not_extracted(staff_client, design):
    with patch.object(FusionCadExtractor, 'extract') as extract:
        _upload(staff_client, design, 'MyBoard.f3z', asset_type=DesignAsset.ATTACHMENT)

    extract.assert_not_called()
    design.refresh_from_db()
    assert design.cad_tool == ''


class _OtherToolExtractor(CadExtractor):
    cad_tool = 'OTHER'
    project_label = 'Other Tool Project'
    file_extensions = ('.other',)


@pytest.mark.django_db
def test_project_file_for_a_different_cad_tool_is_refused(staff_client, design, monkeypatch):
    monkeypatch.setitem(cad_import.EXTRACTORS, 'OTHER', _OtherToolExtractor())
    design.cad_tool = Design.CAD_FUSION
    design.save()
    existing = DesignAsset(design=design, name='old', asset_type=DesignAsset.CAD_PROJECT)
    existing.file.save('old.f3z', ContentFile(b'old'), save=True)

    response = _upload(staff_client, design, 'MyBoard.other')

    assert list(design.designasset_set.values_list('pk', flat=True)) == [existing.pk]
    design.refresh_from_db()
    assert design.cad_tool == Design.CAD_FUSION
    assert 'but that file is a Other Tool Project' in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize('cad_tool, label', [
    (Design.CAD_FUSION, 'Fusion Electronics Project'),
    ('', 'CAD Project'),
])
def test_design_files_row_label_follows_cad_tool(staff_client, design, cad_tool, label):
    design.cad_tool = cad_tool
    design.save()

    response = staff_client.get(reverse('design_detail', args=[design.pk]))

    assert response.context['core_assets'][0][:2] == (DesignAsset.CAD_PROJECT, label)


@pytest.mark.django_db
def test_fusion_project_row_shows_fusion_icon(staff_client, design):
    design.cad_tool = Design.CAD_FUSION
    design.save()
    asset = DesignAsset(design=design, name='proj', asset_type=DesignAsset.CAD_PROJECT)
    asset.file.save('proj.f3z', ContentFile(b'proj'), save=True)

    response = staff_client.get(reverse('design_detail', args=[design.pk]))

    assert 'img/filetypes/fusion.svg' in response.content.decode()
