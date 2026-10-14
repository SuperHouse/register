import csv
import io
import zipfile
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
import pytest

from crm.models import Org
from device.cad_import import CadImportError, KicadCadExtractor, extractor_for_upload
from device.cad_import import kicad
from device.models import Design, DesignAsset

# A hand-written two-resistor project (R1 on top, R2 underneath), small enough to commit.
# Real client boards stay out of the repo.
FIXTURE_DIR = Path(__file__).parent / 'fixtures' / 'kicad' / 'tiny'


def _zip_bytes(entries):
    """entries: {archive path: bytes}."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _fixture_entries(prefix='tiny/'):
    return {f'{prefix}{p.name}': p.read_bytes() for p in FIXTURE_DIR.iterdir()}


def _write_zip(path, entries):
    path.write_bytes(_zip_bytes(entries))
    return path


def _kicad_cli_available():
    try:
        return kicad.subprocess.run(kicad._kicad_cli() + ['version'], capture_output=True).returncode == 0
    except (FileNotFoundError, OSError):
        return False


needs_kicad_cli = pytest.mark.skipif(
    not _kicad_cli_available(), reason='kicad-cli (KiCad 9 or later) is not installed',
)


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / 'media'


# --- recognising a KiCAD zip ---------------------------------------------------------------

def test_accepts_only_zips_holding_a_project_file():
    extractor = KicadCadExtractor()

    with_project = SimpleUploadedFile('board.zip', _zip_bytes(_fixture_entries()))
    assert extractor.accepts(with_project)
    assert with_project.tell() == 0

    assert not extractor.accepts(SimpleUploadedFile('gerbers.zip', _zip_bytes({'board.gtl': b'G04*'})))
    assert not extractor.accepts(SimpleUploadedFile('broken.zip', b'not a zip'))
    # A project file only inside KiCad's automatic backups folder doesn't count.
    assert not extractor.accepts(SimpleUploadedFile('old.zip', _zip_bytes({'x-backups/x.kicad_pro': b'{}'})))


def test_extractor_for_upload_picks_kicad_for_a_project_zip():
    upload = SimpleUploadedFile('board.zip', _zip_bytes(_fixture_entries()))
    assert isinstance(extractor_for_upload(upload), KicadCadExtractor)


# --- unpacking -----------------------------------------------------------------------------

@pytest.mark.parametrize('bad_name', ['../escape.txt', '/etc/escape.txt', 'tiny/../../escape.txt'])
def test_unpack_refuses_paths_outside_the_destination(tmp_path, bad_name):
    archive = _write_zip(tmp_path / 'bad.zip', {bad_name: b'x'})
    with pytest.raises(CadImportError, match='unsafe path'):
        kicad._safe_unpack(archive, tmp_path / 'out')
    assert not (tmp_path / 'escape.txt').exists()


def test_unpack_refuses_oversized_archives(tmp_path, monkeypatch):
    monkeypatch.setattr(kicad, 'MAX_UNPACKED_BYTES', 10)
    archive = _write_zip(tmp_path / 'big.zip', {'big.bin': b'x' * 11})
    with pytest.raises(CadImportError, match='more than'):
        kicad._safe_unpack(archive, tmp_path / 'out')


def test_unpack_skips_backups_and_macos_metadata(tmp_path):
    archive = _write_zip(tmp_path / 'p.zip', {
        'p/p.kicad_pro': b'{}',
        'p/p-backups/p-2026.zip': b'old',
        '__MACOSX/p/._p.kicad_pro': b'meta',
    })
    kicad._safe_unpack(archive, tmp_path / 'out')
    files = sorted(p.relative_to(tmp_path / 'out').as_posix() for p in (tmp_path / 'out').rglob('*') if p.is_file())
    assert files == ['p/p.kicad_pro']


# --- finding the project -------------------------------------------------------------------

def _tree(root, names):
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{}')
    return root


def test_find_project_in_a_nested_folder(tmp_path):
    root = _tree(tmp_path, ['MyBoard/MyBoard.kicad_pro'])
    assert kicad._find_project_file(root, 'upload') == root / 'MyBoard/MyBoard.kicad_pro'


def test_find_project_prefers_the_one_named_like_the_upload(tmp_path):
    root = _tree(tmp_path, ['a/main.kicad_pro', 'b/MyBoard.kicad_pro'])
    assert kicad._find_project_file(root, 'MyBoard') == root / 'b/MyBoard.kicad_pro'


def test_find_project_falls_back_to_the_shallowest(tmp_path):
    root = _tree(tmp_path, ['main.kicad_pro', 'panel/panel.kicad_pro'])
    assert kicad._find_project_file(root, 'upload') == root / 'main.kicad_pro'


def test_find_project_refuses_ambiguous_archives(tmp_path):
    root = _tree(tmp_path, ['a/a.kicad_pro', 'b/b.kicad_pro'])
    with pytest.raises(CadImportError, match='more than one KiCAD project'):
        kicad._find_project_file(root, 'upload')


def test_find_project_explains_kicad_5_projects(tmp_path):
    root = _tree(tmp_path, ['old/old.pro'])
    with pytest.raises(CadImportError, match='KiCad 5'):
        kicad._find_project_file(root, 'upload')


def test_missing_board_file_fails(tmp_path):
    archive = _write_zip(tmp_path / 'tiny.zip', {'tiny/tiny.kicad_pro': b'{}'})
    with pytest.raises(CadImportError, match='No tiny.kicad_pcb'):
        KicadCadExtractor().extract(archive, tmp_path / 'work')


# --- running kicad-cli ---------------------------------------------------------------------

def test_missing_kicad_cli_is_reported(tmp_path, settings):
    settings.KICAD_CLI = [str(tmp_path / 'no-such-kicad-cli')]
    archive = _write_zip(tmp_path / 'tiny.zip', _fixture_entries())
    with pytest.raises(CadImportError, match='kicad-cli not found'):
        KicadCadExtractor().extract(archive, tmp_path / 'work')


def test_failing_kicad_cli_is_reported(tmp_path, settings):
    settings.KICAD_CLI = ['false']
    archive = _write_zip(tmp_path / 'tiny.zip', _fixture_entries())
    with pytest.raises(CadImportError, match='failed'):
        KicadCadExtractor().extract(archive, tmp_path / 'work')


@needs_kicad_cli
def test_extract_real_project(tmp_path):
    archive = _write_zip(tmp_path / 'tiny.zip', {**_fixture_entries(), 'tiny/tiny-backups/old.zip': b'x'})

    extracted = KicadCadExtractor().extract(archive, tmp_path / 'work')

    assert extracted.pcb_design.name == 'tiny.kicad_pcb'
    assert extracted.schematic.name == 'tiny.kicad_sch'
    rows = list(csv.DictReader(io.StringIO(extracted.bom.read_text())))
    assert rows == [{
        'reference': 'R1', 'device': 'R', 'package': 'Resistor_SMD:R_0603_1608Metric',
        'value': '10k', 'library': 'Device',
    }]
    for render in (extracted.pcb_top, extracted.pcb_bottom, extracted.pcb_3d):
        with Image.open(render) as image:
            assert image.mode == 'RGBA'
            # Trimmed to the board, not left at the full render canvas size.
            assert image.width < kicad.RENDER_SIZE and image.height < kicad.RENDER_SIZE


# --- uploading through the Design page -----------------------------------------------------

@pytest.mark.django_db
@needs_kicad_cli
def test_kicad_zip_upload_fills_design_files(client, django_user_model):
    org = Org.objects.create(company_name='KiCAD Upload Org')
    design = Design.objects.create(client=org, sku='KC1', name='KiCAD Upload Design', hw_version='1.0')
    staff = django_user_model.objects.create_user(email='staff@example.com', password='staffy', is_staff=True)
    client.force_login(staff)

    response = client.post(
        reverse('design_asset_add', args=[design.pk]),
        {
            'file': SimpleUploadedFile('Tiny-v1.zip', _zip_bytes(_fixture_entries())),
            'name': 'Tiny-v1',
            'asset_type': DesignAsset.CAD_PROJECT,
        },
        follow=True,
    )

    design.refresh_from_db()
    assert design.cad_tool == Design.CAD_KICAD
    filenames = {a.asset_type: a.filename for a in design.designasset_set.all()}
    assert filenames == {
        DesignAsset.CAD_PROJECT: 'Tiny-v1.zip',
        DesignAsset.PCB_DESIGN: 'Tiny-v1.kicad_pcb',
        DesignAsset.SCHEMATIC: 'Tiny-v1.kicad_sch',
        DesignAsset.BOM: 'Tiny-v1.csv',
        DesignAsset.PCB_TOP: 'Tiny-v1-top.png',
        DesignAsset.PCB_BOTTOM: 'Tiny-v1-bottom.png',
        DesignAsset.PCB_3D: 'Tiny-v1-3d.png',
    }
    assert 'Extracted from KiCAD Project' in response.content.decode()


@pytest.mark.django_db
def test_kicad_zip_replaces_a_fusion_project(client, django_user_model):
    org = Org.objects.create(company_name='Mixed Tool Org')
    design = Design.objects.create(client=org, sku='MX1', name='Mixed Tool Design', hw_version='1.0')
    design.cad_tool = Design.CAD_FUSION
    design.save()
    staff = django_user_model.objects.create_user(email='staff@example.com', password='staffy', is_staff=True)
    client.force_login(staff)

    with patch.object(KicadCadExtractor, 'extract', return_value=kicad.ExtractedAssets()) as extract:
        client.post(
            reverse('design_asset_add', args=[design.pk]),
            {
                'file': SimpleUploadedFile('Tiny.zip', _zip_bytes(_fixture_entries())),
                'name': 'Tiny',
                'asset_type': DesignAsset.CAD_PROJECT,
            },
        )

    extract.assert_called_once()
    design.refresh_from_db()
    assert design.cad_tool == Design.CAD_KICAD
