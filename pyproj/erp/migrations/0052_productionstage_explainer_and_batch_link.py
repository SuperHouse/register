# register#152, step 1 of 3: new ProductionStage fields, plus a nullable link from
# BatchProductionStage to its ProductionStage (filled in by 0053, required by 0054).

import django.db.models.deletion
from django.db import migrations, models

import erp.models


class Migration(migrations.Migration):

    dependencies = [
        ("erp", "0051_library_labels_tool_neutral"),
    ]

    operations = [
        migrations.AddField(
            model_name="productionstage",
            name="icon",
            field=models.CharField(
                blank=True,
                help_text='A Bootstrap Icons (e.g. "bi-truck") or CoreUI Icons (e.g. "cil-puzzle") name, shown on the colour',
                max_length=50,
            ),
        ),
        migrations.AddField(
            model_name="productionstage",
            name="active",
            field=models.BooleanField(
                default=True,
                help_text="Inactive stages can't be added to batches or templates, but still show on batches that use them",
            ),
        ),
        migrations.AddField(
            model_name="productionstage",
            name="explanation",
            field=models.TextField(blank=True, help_text="Shown to users who click the info icon next to this stage"),
        ),
        migrations.AddField(
            model_name="productionstage",
            name="explanation_image",
            field=models.ImageField(blank=True, upload_to=erp.models.production_stage_media_upload_path),
        ),
        migrations.AddField(
            model_name="productionstage",
            name="explanation_video_url",
            field=models.URLField(blank=True, help_text="A YouTube link. Unlisted videos work."),
        ),
        migrations.AddField(
            model_name="productionstage",
            name="explanation_video_loop",
            field=models.BooleanField(
                default=False,
                help_text="Play the video as a silent looping clip with no controls, like a GIF",
            ),
        ),
        migrations.AddField(
            model_name="batchproductionstage",
            name="production_stage",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="batch_stages",
                to="erp.productionstage",
            ),
        ),
    ]
