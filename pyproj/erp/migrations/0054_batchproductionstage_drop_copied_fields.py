# register#152, step 3 of 3: every BatchProductionStage now has a ProductionStage (0053),
# so make the link required and drop the copied name and colour.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("erp", "0053_link_batch_stages_to_production_stages"),
    ]

    operations = [
        migrations.AlterField(
            model_name="batchproductionstage",
            name="production_stage",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="batch_stages",
                to="erp.productionstage",
            ),
        ),
        migrations.RemoveField(
            model_name="batchproductionstage",
            name="name",
        ),
        migrations.RemoveField(
            model_name="batchproductionstage",
            name="color",
        ),
    ]
