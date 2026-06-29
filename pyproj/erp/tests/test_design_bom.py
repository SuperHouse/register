from decimal import Decimal

from django.contrib.messages import get_messages
from django.core.files.base import ContentFile
from django.db import IntegrityError
from django.urls import reverse
import pytest

from crm.models import Org
from device.models import Design, DesignAsset
from erp.models import DesignBomEntry, Part


BOM_CSV = (
    'reference,device,package,value,library\n'
    'R1,RES,0402,10k,Resistor\n'
    'R2,RES,0402,10k,Resistor\n'
    'C1,CAP,0603,100nF,Capacitor\n'
)

BRD_XML = '''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE eagle SYSTEM "eagle.dtd">
<eagle version="9.7.0">
<drawing>
<settings></settings>
<grid/>
<layers></layers>
<board>
<elements>
<element name="R1" library="Resistor" package="0402" value="10k" x="10.5" y="20" rot="R90"/>
<element name="R2" library="Resistor" package="0402" value="10k" x="15" y="20.25" rot="MR180"/>
<element name="C1" library="Capacitor" package="0603" value="100nF" x="30" y="40"/>
</elements>
</board>
</drawing>
</eagle>
'''


@pytest.fixture
def design():
    org = Org.objects.create(company_name='BOM Test Org')
    return Design.objects.create(client=org, sku='BOM1', name='BOM Test Design', hw_version='1.0')


@pytest.fixture
def design_with_bom_csv(design):
    asset = DesignAsset(design=design, name='bom', asset_type=DesignAsset.BOM)
    asset.file.save('bom.csv', ContentFile(BOM_CSV.encode()), save=True)
    return design


@pytest.fixture
def design_with_bom_csv_and_brd(design_with_bom_csv):
    asset = DesignAsset(design=design_with_bom_csv, name='brd', asset_type=DesignAsset.PCB_DESIGN)
    asset.file.save('design.brd', ContentFile(BRD_XML.encode()), save=True)
    return design_with_bom_csv


@pytest.fixture
def staff_user(django_user_model):
    return django_user_model.objects.create_user(email='staff@example.com', password='staffy', is_staff=True)


@pytest.mark.django_db
def test_unique_constraint_on_design_and_reference(design):
    part = Part.objects.create(name='10k', value='10k')
    DesignBomEntry.objects.create(design=design, part=part, reference='R1')

    with pytest.raises(IntegrityError):
        DesignBomEntry.objects.create(design=design, part=part, reference='R1')


@pytest.mark.django_db
def test_populate_from_bom_creates_entries_and_parts(client, staff_user, design_with_bom_csv):
    client.force_login(staff_user)

    response = client.post(reverse('erp:design_bom_populate', args=[design_with_bom_csv.pk]))
    assert response.status_code == 302

    entries = DesignBomEntry.objects.filter(design=design_with_bom_csv).order_by('reference')
    assert list(entries.values_list('reference', flat=True)) == ['C1', 'R1', 'R2']
    assert entries.get(reference='R1').part.value == '10k'
    assert entries.get(reference='C1').part.value == '100nF'
    # R1 and R2 share the same resolved part (same device/package/value).
    assert entries.get(reference='R1').part_id == entries.get(reference='R2').part_id


@pytest.mark.django_db
def test_populate_from_bom_reports_new_parts_created(client, staff_user, design_with_bom_csv):
    client.force_login(staff_user)
    assert Part.objects.count() == 0

    response = client.post(reverse('erp:design_bom_populate', args=[design_with_bom_csv.pk]))

    # Two distinct (device, package, value) combinations across the three rows -> two new parts.
    assert Part.objects.count() == 2
    messages = [str(m) for m in get_messages(response.wsgi_request)]
    assert any('2 new parts created in the Parts library.' in m for m in messages)


@pytest.mark.django_db
def test_populate_from_bom_does_not_report_new_parts_when_none_created(client, staff_user, design_with_bom_csv):
    client.force_login(staff_user)
    Part.objects.create(name='10k', device='RES', package='0402', value='10k')
    Part.objects.create(name='100nF', device='CAP', package='0603', value='100nF')

    response = client.post(reverse('erp:design_bom_populate', args=[design_with_bom_csv.pk]))

    assert Part.objects.count() == 2
    messages = [str(m) for m in get_messages(response.wsgi_request)]
    assert any('new part' not in m for m in messages)


@pytest.mark.django_db
def test_populate_from_bom_is_safe_to_rerun_without_clobbering_edits(client, staff_user, design_with_bom_csv):
    client.force_login(staff_user)
    client.post(reverse('erp:design_bom_populate', args=[design_with_bom_csv.pk]))

    # Manually repoint R1 at a different part, simulating a user edit.
    other_part = Part.objects.create(name='Manually chosen part', value='manual')
    r1 = DesignBomEntry.objects.get(design=design_with_bom_csv, reference='R1')
    r1.part = other_part
    r1.save()

    response = client.post(reverse('erp:design_bom_populate', args=[design_with_bom_csv.pk]))
    assert response.status_code == 302

    r1.refresh_from_db()
    assert r1.part_id == other_part.pk
    assert DesignBomEntry.objects.filter(design=design_with_bom_csv).count() == 3


@pytest.mark.django_db
def test_populate_from_bom_backfills_positions_from_brd(client, staff_user, design_with_bom_csv_and_brd):
    client.force_login(staff_user)

    response = client.post(reverse('erp:design_bom_populate', args=[design_with_bom_csv_and_brd.pk]))
    assert response.status_code == 302

    r1 = DesignBomEntry.objects.get(design=design_with_bom_csv_and_brd, reference='R1')
    assert r1.pos_x == Decimal('10.5')
    assert r1.pos_y == Decimal('20')
    assert r1.rotation == Decimal('90')
    assert r1.side == DesignBomEntry.TOP

    r2 = DesignBomEntry.objects.get(design=design_with_bom_csv_and_brd, reference='R2')
    assert r2.rotation == Decimal('180')
    assert r2.side == DesignBomEntry.BOTTOM

    c1 = DesignBomEntry.objects.get(design=design_with_bom_csv_and_brd, reference='C1')
    assert c1.rotation == Decimal('0')
    assert c1.side == DesignBomEntry.TOP


@pytest.mark.django_db
def test_populate_from_bom_without_brd_leaves_positions_unset(client, staff_user, design_with_bom_csv):
    client.force_login(staff_user)

    client.post(reverse('erp:design_bom_populate', args=[design_with_bom_csv.pk]))

    r1 = DesignBomEntry.objects.get(design=design_with_bom_csv, reference='R1')
    assert r1.pos_x is None
    assert r1.rotation is None
    assert r1.side == ''


@pytest.mark.django_db
def test_populate_from_bom_warns_when_no_csv_uploaded(client, staff_user, design):
    client.force_login(staff_user)

    response = client.post(reverse('erp:design_bom_populate', args=[design.pk]))
    assert response.status_code == 302
    assert DesignBomEntry.objects.filter(design=design).count() == 0


@pytest.mark.django_db
def test_entry_add_edit_delete_require_staff(client, django_user_model, design):
    part = Part.objects.create(name='10k', value='10k')
    non_staff = django_user_model.objects.create_user(email='user@example.com', password='pass')
    client.force_login(non_staff)

    add_url = reverse('erp:design_bom_entry_add', args=[design.pk])
    response = client.post(add_url, {'reference': 'R1', 'part': part.pk})
    assert response.status_code == 302
    assert DesignBomEntry.objects.filter(design=design).count() == 0

    entry = DesignBomEntry.objects.create(design=design, part=part, reference='R1')

    edit_url = reverse('erp:design_bom_entry_edit', args=[entry.pk])
    client.post(edit_url, {'reference': 'R1-renamed', 'part': part.pk})
    entry.refresh_from_db()
    assert entry.reference == 'R1'

    delete_url = reverse('erp:design_bom_entry_delete', args=[entry.pk])
    client.post(delete_url)
    assert DesignBomEntry.objects.filter(pk=entry.pk).exists()


@pytest.mark.django_db
def test_staff_can_add_edit_delete_entries(client, staff_user, design):
    client.force_login(staff_user)
    part = Part.objects.create(name='10k', value='10k')
    other_part = Part.objects.create(name='100nF', value='100nF')

    add_url = reverse('erp:design_bom_entry_add', args=[design.pk])
    client.post(add_url, {'reference': 'R1', 'part': part.pk})
    entry = DesignBomEntry.objects.get(design=design, reference='R1')

    edit_url = reverse('erp:design_bom_entry_edit', args=[entry.pk])
    client.post(edit_url, {'reference': 'R1', 'part': other_part.pk})
    entry.refresh_from_db()
    assert entry.part_id == other_part.pk

    delete_url = reverse('erp:design_bom_entry_delete', args=[entry.pk])
    client.post(delete_url)
    assert not DesignBomEntry.objects.filter(pk=entry.pk).exists()


@pytest.mark.django_db
def test_part_import_bom_still_works_after_refactor(client, staff_user):
    """Regression test: part_import_bom's added/skipped/excluded counting must be unchanged
    after extracting its per-row logic into the shared _resolve_bom_csv_row() helper."""
    client.force_login(staff_user)

    csv_file = ContentFile(BOM_CSV.encode(), name='bom.csv')
    response = client.post(reverse('erp:part_import_bom'), {'csv_file': csv_file})
    assert response.status_code == 302

    # Two distinct (device, package, value) combinations -> two parts created.
    assert Part.objects.filter(value='10k').count() == 1
    assert Part.objects.filter(value='100nF').count() == 1

    # Re-importing the same CSV should now skip both as duplicates, adding nothing.
    csv_file = ContentFile(BOM_CSV.encode(), name='bom.csv')
    client.post(reverse('erp:part_import_bom'), {'csv_file': csv_file})
    assert Part.objects.filter(value='10k').count() == 1
    assert Part.objects.filter(value='100nF').count() == 1
