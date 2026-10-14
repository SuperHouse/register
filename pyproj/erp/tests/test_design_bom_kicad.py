"""Populate BOM for KiCAD designs (issue #143): BOM rows from the extracted KiCAD BOM CSV, and
positions from the .kicad_pcb via kicad-cli. The Fusion/EAGLE equivalents are in
test_design_bom.py."""
from decimal import Decimal
from pathlib import Path

from django.contrib.messages import get_messages
from django.core.files.base import ContentFile
from django.urls import reverse
import pytest

from crm.models import Org
from device.cad_import import SIDE_BOTTOM, SIDE_TOP, FusionCadExtractor, Placement, read_placements
from device.cad_import import kicad
from device.models import Design, DesignAsset
from erp.models import DesignBomEntry

FIXTURE_BOARD = Path(__file__).resolve().parents[2] / 'device' / 'tests' / 'fixtures' / 'kicad' / 'tiny' / 'tiny.kicad_pcb'

# What KicadCadExtractor writes for the fixture project, plus R2 (on the underside of the
# fixture board, but not in its one-symbol schematic).
KICAD_BOM_CSV = (
    '"reference","device","package","value","library"\n'
    '"R1","R","Resistor_SMD:R_0603_1608Metric","10k","Device"\n'
    '"R2","R","Resistor_SMD:R_0603_1608Metric","1k","Device"\n'
)


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


@pytest.fixture
def kicad_design():
    org = Org.objects.create(company_name='KiCAD BOM Org')
    design = Design.objects.create(client=org, sku='KB1', name='KiCAD BOM Design', hw_version='1.0')
    design.cad_tool = Design.CAD_KICAD
    design.save()
    bom = DesignAsset(design=design, name='tiny', asset_type=DesignAsset.BOM)
    bom.file.save('tiny.csv', ContentFile(KICAD_BOM_CSV.encode()), save=True)
    board = DesignAsset(design=design, name='tiny', asset_type=DesignAsset.PCB_DESIGN)
    board.file.save('tiny.kicad_pcb', ContentFile(FIXTURE_BOARD.read_bytes()), save=True)
    return design


@pytest.fixture
def staff_client(client, django_user_model):
    staff = django_user_model.objects.create_user(email='staff@example.com', password='staffy', is_staff=True)
    client.force_login(staff)
    return client


# --- reading placements --------------------------------------------------------------------

def test_read_placements_picks_the_reader_from_the_file_extension(tmp_path):
    assert read_placements(tmp_path / 'notes.pdf') is None

    brd = tmp_path / 'board.brd'
    brd.write_text('not xml')
    assert read_placements(brd) == {}  # an unreadable .brd gives no positions, as before


@needs_kicad_cli
def test_kicad_placements_from_real_board():
    placements = read_placements(FIXTURE_BOARD)

    # Millimetres, Y up from the page origin (the fixture sets no drill/place origin).
    assert placements == {
        'R1': Placement(Decimal('105.0000'), Decimal('-105.0000'), Decimal('90.00'), SIDE_TOP),
        'R2': Placement(Decimal('115.0000'), Decimal('-105.0000'), Decimal('0.00'), SIDE_BOTTOM),
    }


def test_kicad_rotation_is_normalised_like_eagle(tmp_path, monkeypatch):
    def fake_run_cli(args, output, cwd):
        Path(output).write_text(
            'Ref,Val,Package,PosX,PosY,Rot,Side\n'
            '"J1","Jack","BarrelJack",48.260000,-45.720000,-90.000000,top\n'
            '"",ignored,,1,1,0,top\n'
        )
    monkeypatch.setattr(kicad, '_run_cli', fake_run_cli)
    board = tmp_path / 'b.kicad_pcb'
    board.write_text('(kicad_pcb)')

    placements = read_placements(board)

    assert placements == {'J1': Placement(Decimal('48.2600'), Decimal('-45.7200'), Decimal('270.00'), SIDE_TOP)}


def test_eagle_reader_moved_without_changing_results(tmp_path):
    from erp.tests.test_design_bom import BRD_XML
    brd = tmp_path / 'design.brd'
    brd.write_text(BRD_XML)

    placements = FusionCadExtractor().read_placements(brd)

    assert placements['R1'] == Placement(Decimal('10.5'), Decimal('20'), Decimal('90'), SIDE_TOP)
    assert placements['R2'] == Placement(Decimal('15'), Decimal('20.25'), Decimal('180'), SIDE_BOTTOM)
    assert placements['C1'] == Placement(Decimal('30'), Decimal('40'), Decimal('0'), SIDE_TOP)


# --- Populate BOM --------------------------------------------------------------------------

@pytest.mark.django_db
@needs_kicad_cli
def test_populate_kicad_design_creates_entries_with_positions(staff_client, kicad_design):
    response = staff_client.post(reverse('erp:design_bom_populate', args=[kicad_design.pk]))
    assert response.status_code == 302

    r1 = DesignBomEntry.objects.get(design=kicad_design, reference='R1')
    assert r1.part.value == '10k'
    assert r1.part.package == 'Resistor_SMD:R_0603_1608Metric'
    assert r1.part.name == '10k R_0603_1608Metric R'  # library prefix dropped from the name only
    assert r1.part.fusion_library == 'Device'
    assert (r1.pos_x, r1.pos_y, r1.rotation, r1.side) == (
        Decimal('105'), Decimal('-105'), Decimal('90'), DesignBomEntry.TOP,
    )
    r2 = DesignBomEntry.objects.get(design=kicad_design, reference='R2')
    assert r2.side == DesignBomEntry.BOTTOM

    text = ' '.join(str(m) for m in get_messages(response.wsgi_request))
    assert '2 entries added' in text
    assert '2 positions updated from PCB design file.' in text


@pytest.mark.django_db
def test_populate_keeps_bom_rows_when_positions_fail(staff_client, kicad_design, settings):
    settings.KICAD_CLI = ['false']

    response = staff_client.post(reverse('erp:design_bom_populate', args=[kicad_design.pk]))

    entries = DesignBomEntry.objects.filter(design=kicad_design)
    assert entries.count() == 2
    assert all(e.pos_x is None for e in entries)
    text = ' '.join(str(m) for m in get_messages(response.wsgi_request))
    assert 'BOM populated: 2 entries added' in text
    assert 'Positions were not updated: kicad-cli pcb export failed' in text
