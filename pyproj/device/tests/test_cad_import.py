from unittest.mock import patch

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
import pytest

from crm.models import Org
from device import cad_import
from device.cad_import import (
    CadExtractor, CadImportError, ExtractedAssets, FusionCadExtractor, extractor_for_upload,
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


def test_extractor_for_upload():
    def upload(name):
        return SimpleUploadedFile(name, b'not a zip')

    assert isinstance(extractor_for_upload(upload('board.f3z')), FusionCadExtractor)
    assert isinstance(extractor_for_upload(upload('BOARD.F3Z')), FusionCadExtractor)
    assert extractor_for_upload(upload('board.zip')) is None  # a .zip must hold a .kicad_pro
    assert extractor_for_upload(upload('board')) is None


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
        response = _upload(staff_client, design, 'notes.pdf')

    extract.assert_not_called()
    design.refresh_from_db()
    assert design.cad_tool == ''
    assert list(design.designasset_set.values_list('asset_type', flat=True)) == [DesignAsset.CAD_PROJECT]
    assert 'Not a recognised CAD project' in response.content.decode()


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

    def extract(self, project_path, out_dir):
        return ExtractedAssets()


@pytest.mark.django_db
def test_cad_tool_follows_the_uploaded_project_file(staff_client, design, monkeypatch):
    """A design that moves to another tool just gets the new project uploaded - the flag is
    set from the file, never chosen by hand."""
    monkeypatch.setitem(cad_import.EXTRACTORS, 'OTHER', _OtherToolExtractor())
    design.cad_tool = Design.CAD_FUSION
    design.save()
    existing = DesignAsset(design=design, name='old', asset_type=DesignAsset.CAD_PROJECT)
    existing.file.save('old.f3z', ContentFile(b'old'), save=True)

    _upload(staff_client, design, 'MyBoard.other')

    design.refresh_from_db()
    assert design.cad_tool == 'OTHER'
    project_files = list(design.designasset_set.filter(asset_type=DesignAsset.CAD_PROJECT))
    assert [a.filename for a in project_files] == ['MyBoard.other']


@pytest.mark.django_db
def test_unrecognised_project_file_clears_cad_tool(staff_client, design):
    design.cad_tool = Design.CAD_FUSION
    design.save()

    _upload(staff_client, design, 'notes.pdf')

    design.refresh_from_db()
    assert design.cad_tool == ''


@pytest.mark.django_db
def test_deleting_the_project_file_clears_cad_tool(staff_client, design):
    design.cad_tool = Design.CAD_FUSION
    design.save()
    project = DesignAsset(design=design, name='proj', asset_type=DesignAsset.CAD_PROJECT)
    project.file.save('proj.f3z', ContentFile(b'proj'), save=True)
    bom = DesignAsset(design=design, name='bom', asset_type=DesignAsset.BOM)
    bom.file.save('bom.csv', ContentFile(b'bom'), save=True)

    staff_client.post(reverse('design_asset_delete', args=[bom.pk]))
    design.refresh_from_db()
    assert design.cad_tool == Design.CAD_FUSION  # only the project file decides

    staff_client.post(reverse('design_asset_delete', args=[project.pk]))
    design.refresh_from_db()
    assert design.cad_tool == ''


@pytest.mark.django_db
def test_cad_tool_is_not_on_the_design_forms(staff_client, design):
    from device.forms import DesignAddForm, DesignDetailsForm
    assert 'cad_tool' not in DesignDetailsForm().fields
    assert 'cad_tool' not in DesignAddForm().fields

    response = staff_client.post(reverse('design_update', args=[design.pk]), {
        'sku': design.sku, 'cad_tool': Design.CAD_FUSION,
        'assembly_time_minutes': 0, 'additional_materials': 0, 'pcb_cost': 0, 'packaging': 0,
    })
    assert response.status_code == 302
    design.refresh_from_db()
    assert design.cad_tool == ''  # a posted value is ignored


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


@pytest.mark.django_db
def test_kicad_project_row_shows_kicad_icon(staff_client, design):
    design.cad_tool = Design.CAD_KICAD
    design.save()
    asset = DesignAsset(design=design, name='proj', asset_type=DesignAsset.CAD_PROJECT)
    asset.file.save('proj.zip', ContentFile(b'proj'), save=True)

    response = staff_client.get(reverse('design_detail', args=[design.pk]))

    assert 'img/filetypes/kicad.svg' in response.content.decode()
