from django.db import migrations, models


def convert_legacy_types(apps, schema_editor):
    DesignAsset = apps.get_model('device', 'DesignAsset')
    DesignAsset.objects.filter(asset_type__in=['IMAGE', 'DOC', 'OTHER']).update(asset_type='ATTACHMENT')


class Migration(migrations.Migration):

    dependencies = [
        ('device', '0028_add_pcb_design_schematic_preview_asset_types'),
    ]

    operations = [
        migrations.RunPython(convert_legacy_types, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='designasset',
            name='asset_type',
            field=models.CharField(
                choices=[
                    ('Design Files', [
                        ('PCB_3D', 'PCB 3D View'),
                        ('PCB_TOP', 'PCB Top View'),
                        ('PCB_BOTTOM', 'PCB Bottom View'),
                        ('FUSION', 'Fusion Electronics Project'),
                        ('SCHEMATIC', 'Schematic Design File'),
                        ('PCB_DESIGN', 'PCB Design File'),
                        ('BOM', 'Bill of Materials'),
                        ('FIRMWARE', 'Firmware Binary'),
                    ]),
                    ('Additional', [
                        ('ATTACHMENT', 'Attachment'),
                    ]),
                ],
                default='ATTACHMENT',
                max_length=20,
            ),
        ),
    ]
