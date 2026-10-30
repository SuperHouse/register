# register#152, step 2 of 3: link each BatchProductionStage to the ProductionStage it was
# copied from, matching on name (ProductionStage.name is unique). A batch stage whose name
# matches no stage type (the type was renamed or deleted after the batch stage was copied)
# gets a new, inactive stage type with its name and colour, so no batch loses a stage.

from django.db import migrations


def link_batch_stages(apps, schema_editor):
    ProductionStage = apps.get_model("erp", "ProductionStage")
    BatchProductionStage = apps.get_model("erp", "BatchProductionStage")

    stages_by_name = {stage.name: stage for stage in ProductionStage.objects.all()}
    last_stage = ProductionStage.objects.order_by("-order").first()
    next_order = (last_stage.order + 1) if last_stage else 1

    for batch_stage in BatchProductionStage.objects.filter(production_stage__isnull=True):
        stage = stages_by_name.get(batch_stage.name)
        if stage is None:
            stage = ProductionStage.objects.create(
                name=batch_stage.name,
                color=batch_stage.color,
                order=next_order,
                active=False,
            )
            stages_by_name[stage.name] = stage
            next_order += 1
        batch_stage.production_stage = stage
        batch_stage.save(update_fields=["production_stage"])


def copy_names_back(apps, schema_editor):
    BatchProductionStage = apps.get_model("erp", "BatchProductionStage")

    for batch_stage in BatchProductionStage.objects.select_related("production_stage"):
        batch_stage.name = batch_stage.production_stage.name
        batch_stage.color = batch_stage.production_stage.color
        batch_stage.save(update_fields=["name", "color"])


class Migration(migrations.Migration):

    dependencies = [
        ("erp", "0052_productionstage_explainer_and_batch_link"),
    ]

    operations = [
        migrations.RunPython(link_batch_stages, copy_names_back),
    ]
