# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("erp", "0002_operationtemplate_operationtemplatestep"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="Operation",
            new_name="ProductionStage",
        ),
        migrations.RenameModel(
            old_name="OperationTemplate",
            new_name="ProductionStageTemplate",
        ),
        migrations.RenameModel(
            old_name="OperationTemplateStep",
            new_name="ProductionStageTemplateStep",
        ),
        migrations.RenameField(
            model_name="productionstagetemplatestep",
            old_name="operation",
            new_name="production_stage",
        ),
        migrations.AlterField(
            model_name="productionstage",
            name="color",
            field=models.CharField(
                default="#6c757d",
                help_text="Used to highlight this production stage in the UI",
                max_length=7,
            ),
        ),
    ]
