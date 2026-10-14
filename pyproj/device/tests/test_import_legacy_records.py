import json
import zipfile

from django.core import management, serializers
import pytest

from crm.models import Org
from device.management.commands.import_data import _upgrade_legacy_records
from device.models import Design, DesignAsset


def test_upgrade_converts_fusion_assets_and_sets_cad_tool():
    data = [
        {'model': 'device.design', 'pk': 1, 'fields': {'sku': 'A'}},
        {'model': 'device.design', 'pk': 2, 'fields': {'sku': 'B'}},
        {'model': 'device.design', 'pk': 3, 'fields': {'sku': 'C', 'cad_tool': 'OTHER'}},
        {'model': 'device.designasset', 'pk': 10, 'fields': {'design': 1, 'asset_type': 'FUSION'}},
        {'model': 'device.designasset', 'pk': 11, 'fields': {'design': 2, 'asset_type': 'BOM'}},
        {'model': 'device.designasset', 'pk': 12, 'fields': {'design': 3, 'asset_type': 'FUSION'}},
    ]

    _upgrade_legacy_records(data)

    assert data[0]['fields']['cad_tool'] == 'FUSION'
    assert 'cad_tool' not in data[1]['fields']
    assert data[2]['fields']['cad_tool'] == 'OTHER'  # an explicit value is never overwritten
    assert data[3]['fields']['asset_type'] == 'CAD_PROJECT'
    assert data[4]['fields']['asset_type'] == 'BOM'
    assert data[5]['fields']['asset_type'] == 'CAD_PROJECT'


@pytest.mark.django_db
def test_import_of_pre_0039_export_is_upgraded(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / 'media'

    # Build an export in the pre-0039 shape: no Design.cad_tool, asset_type FUSION.
    org = Org.objects.create(company_name='Legacy Import Org')
    design = Design.objects.create(client=org, sku='LEG1', name='Legacy Design', hw_version='1.0')
    DesignAsset.objects.create(design=design, name='proj', asset_type=DesignAsset.CAD_PROJECT, file='design_assets/x/proj.f3z')
    data = json.loads(serializers.serialize('json', [org, design, *design.designasset_set.all()]))
    for obj in data:
        if obj['model'] == 'device.design':
            del obj['fields']['cad_tool']
        if obj['model'] == 'device.designasset':
            obj['fields']['asset_type'] = 'FUSION'

    archive = tmp_path / 'export.zip'
    with zipfile.ZipFile(archive, 'w') as zf:
        zf.writestr('manifest.json', json.dumps({'export_dt': '', 'app_version': '', 'record_count': len(data)}))
        zf.writestr('data.json', json.dumps(data))

    management.call_command('import_data', str(archive), '--yes')

    design = Design.objects.get(sku='LEG1')
    assert design.cad_tool == Design.CAD_FUSION
    assert list(design.designasset_set.values_list('asset_type', flat=True)) == [DesignAsset.CAD_PROJECT]
