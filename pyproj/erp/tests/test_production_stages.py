# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
"""Production stage types and their use on batches (register#152): batch stages linked to
their stage type, icons, explanations, the active flag, and the explanation image's access rule."""
import io
import os

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.urls import reverse
from PIL import Image
import pytest

from crm.models import Org
from device.models import Design
from erp.models import (
    Batch, BatchProductionStage, ProductionStage, ProductionStageTemplate, ProductionStageTemplateStep,
    youtube_video_id,
)


def png_bytes():
    buffer = io.BytesIO()
    Image.new('RGB', (40, 30), 'red').save(buffer, format='PNG')
    return buffer.getvalue()


@pytest.fixture
def setup(django_user_model):
    org = Org.objects.create(company_name='Stage Org')
    member = django_user_model.objects.create_user(email='member@example.com', password='x')
    org.users.add(member)
    staff = django_user_model.objects.create_user(email='staff@example.com', password='x', is_staff=True)
    design = Design.objects.create(client=org, sku='STG', name='Stage Design', hw_version='1.0')
    batch = Batch.objects.create(design=design, quantity=10)
    smt = ProductionStage.objects.create(name='Top SMT Assembly', color='#ffdd00', order=1)
    test = ProductionStage.objects.create(name='Testing', color='#00ff11', order=2)
    return {'member': member, 'staff': staff, 'batch': batch, 'smt': smt, 'test': test}


# --- Model helpers ---

def test_icon_class_adds_bootstrap_base_class_only():
    assert ProductionStage(icon='bi-truck').icon_class == 'bi bi-truck'
    assert ProductionStage(icon='cil-puzzle').icon_class == 'cil-puzzle'


@pytest.mark.parametrize('color, expected', [
    ('#ffdd00', '#212529'),  # yellow: dark icon
    ('#00ff11', '#212529'),  # bright green: dark icon
    ('#6c757d', '#ffffff'),  # grey: white icon
    ('#0d6efd', '#ffffff'),  # darker blue: white icon
    ('#0085fa', '#212529'),  # lighter blue: dark has slightly more contrast
    ('nonsense', '#ffffff'),
])
def test_icon_color_picks_the_more_readable_of_white_and_dark(color, expected):
    assert ProductionStage(color=color).icon_color == expected


@pytest.mark.parametrize('url', [
    'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
    'https://youtube.com/watch?feature=share&v=dQw4w9WgXcQ',
    'https://youtu.be/dQw4w9WgXcQ?si=abc',
    'https://www.youtube.com/shorts/dQw4w9WgXcQ',
    'https://m.youtube.com/watch?v=dQw4w9WgXcQ',
])
def test_youtube_video_id_accepts_common_link_forms(url):
    assert youtube_video_id(url) == 'dQw4w9WgXcQ'


def test_youtube_video_id_rejects_other_links():
    assert youtube_video_id('https://vimeo.com/123456') is None
    assert youtube_video_id('') is None


def test_youtube_embed_url_normal_and_looping():
    stage = ProductionStage(explanation_video_url='https://youtu.be/dQw4w9WgXcQ')
    assert stage.youtube_embed_url == 'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ?rel=0'
    stage.explanation_video_loop = True
    assert 'loop=1&playlist=dQw4w9WgXcQ' in stage.youtube_embed_url
    assert 'mute=1' in stage.youtube_embed_url


def test_clean_rejects_bad_icon_and_video_link():
    stage = ProductionStage(name='X', icon='truck', explanation_video_url='https://vimeo.com/1')
    with pytest.raises(ValidationError) as excinfo:
        stage.clean()
    assert set(excinfo.value.message_dict) == {'icon', 'explanation_video_url'}


# --- Adding stages to batches ---

@pytest.mark.django_db
def test_add_stage_links_to_stage_type(client, setup):
    client.force_login(setup['staff'])
    client.post(reverse('erp:batch_production_stage_add', args=[setup['batch'].pk]),
                {'production_stage': setup['smt'].pk})
    assert list(setup['batch'].production_stages.values_list('production_stage', flat=True)) == [setup['smt'].pk]


@pytest.mark.django_db
def test_inactive_stage_cannot_be_added_to_a_batch(client, setup):
    setup['smt'].active = False
    setup['smt'].save()
    client.force_login(setup['staff'])
    client.post(reverse('erp:batch_production_stage_add', args=[setup['batch'].pk]),
                {'production_stage': setup['smt'].pk})
    assert not setup['batch'].production_stages.exists()


@pytest.mark.django_db
def test_apply_template_skips_existing_and_inactive_stages(client, setup):
    retired = ProductionStage.objects.create(name='Old Wash', order=3, active=False)
    template = ProductionStageTemplate.objects.create(name='Standard')
    for order, stage in enumerate([setup['smt'], retired, setup['test']], start=1):
        ProductionStageTemplateStep.objects.create(template=template, production_stage=stage, order=order)
    BatchProductionStage.objects.create(batch=setup['batch'], production_stage=setup['smt'], order=1)

    client.force_login(setup['staff'])
    client.post(reverse('erp:batch_apply_template', args=[setup['batch'].pk]), {'template': template.pk})

    stage_ids = list(setup['batch'].production_stages.values_list('production_stage', flat=True))
    assert stage_ids == [setup['smt'].pk, setup['test'].pk]


@pytest.mark.django_db
def test_duplicate_batch_keeps_stage_links_and_resets_progress(client, setup):
    BatchProductionStage.objects.create(
        batch=setup['batch'], production_stage=setup['test'], order=1, status=BatchProductionStage.DONE,
    )
    client.force_login(setup['staff'])
    client.post(reverse('erp:batch_duplicate', args=[setup['batch'].pk]))

    new_batch = Batch.objects.exclude(pk=setup['batch'].pk).get()
    new_stage = new_batch.production_stages.get()
    assert new_stage.production_stage == setup['test']
    assert new_stage.status == BatchProductionStage.NOT_STARTED


@pytest.mark.django_db
def test_stage_type_used_by_a_batch_cannot_be_deleted(client, setup):
    BatchProductionStage.objects.create(batch=setup['batch'], production_stage=setup['smt'], order=1)
    client.force_login(setup['staff'])
    client.post(reverse('erp:production_stage_delete', args=[setup['smt'].pk]))
    assert ProductionStage.objects.filter(pk=setup['smt'].pk).exists()


@pytest.mark.django_db
def test_inline_add_row_creates_an_active_stage(client, setup):
    client.force_login(setup['staff'])
    client.post(reverse('erp:production_stage_list'), {'name': 'Packaging', 'color': '#6c757d'})
    assert ProductionStage.objects.get(name='Packaging').active


# --- Batch page ---

@pytest.mark.django_db
def test_renaming_a_stage_type_shows_on_existing_batches(client, setup):
    BatchProductionStage.objects.create(batch=setup['batch'], production_stage=setup['smt'], order=1)
    setup['smt'].name = 'Top-side SMT'
    setup['smt'].save()
    client.force_login(setup['staff'])
    content = client.get(reverse('erp:batch_edit', args=[setup['batch'].pk])).content.decode()
    assert 'Top-side SMT' in content


@pytest.mark.django_db
@pytest.mark.parametrize('user_key', ['staff', 'member'])
def test_info_button_and_lightbox_only_for_stages_with_an_explanation(client, setup, user_key):
    setup['smt'].explanation = 'Solder paste, pick and place, reflow.'
    setup['smt'].icon = 'bi-layer-backward'
    setup['smt'].save()
    BatchProductionStage.objects.create(batch=setup['batch'], production_stage=setup['smt'], order=1)
    BatchProductionStage.objects.create(batch=setup['batch'], production_stage=setup['test'], order=2)

    client.force_login(setup[user_key])
    content = client.get(reverse('erp:batch_edit', args=[setup['batch'].pk])).content.decode()

    assert f'data-explainer-id="{setup["smt"].pk}"' in content
    assert f'data-explainer-id="{setup["test"].pk}"' not in content
    assert 'id="stage-explainer-modal"' in content
    assert 'Solder paste, pick and place, reflow.' in content
    assert 'bi bi-layer-backward' in content


@pytest.mark.django_db
def test_no_lightbox_when_no_stage_has_an_explanation(client, setup):
    BatchProductionStage.objects.create(batch=setup['batch'], production_stage=setup['test'], order=1)
    client.force_login(setup['staff'])
    content = client.get(reverse('erp:batch_edit', args=[setup['batch'].pk])).content.decode()
    assert 'stage-explainer-modal' not in content


@pytest.mark.django_db
def test_batch_list_data_reports_stage_names(client, setup):
    BatchProductionStage.objects.create(batch=setup['batch'], production_stage=setup['smt'], order=1)
    client.force_login(setup['member'])
    data = client.get(reverse('erp:batch_list_data')).json()
    assert data['batches'][0]['stages'][0]['name'] == 'Top SMT Assembly'


@pytest.mark.django_db
def test_batch_print_lists_stage_names(client, setup):
    BatchProductionStage.objects.create(batch=setup['batch'], production_stage=setup['test'], order=1)
    client.force_login(setup['staff'])
    content = client.get(reverse('erp:batch_print', args=[setup['batch'].pk])).content.decode()
    assert 'Testing' in content


# --- Edit page and explanation image ---

def _edit_data(stage, **overrides):
    data = {'name': stage.name, 'color': stage.color, 'icon': '', 'active': 'on', 'explanation': '',
            'explanation_video_url': ''}
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_edit_page_saves_explanation_fields(client, setup):
    client.force_login(setup['staff'])
    response = client.post(reverse('erp:production_stage_edit', args=[setup['smt'].pk]), _edit_data(
        setup['smt'], icon='cil-puzzle', explanation='Paste and place.',
        explanation_video_url='https://youtu.be/dQw4w9WgXcQ', explanation_video_loop='on',
    ))
    assert response.status_code == 302
    setup['smt'].refresh_from_db()
    assert setup['smt'].icon == 'cil-puzzle'
    assert setup['smt'].explanation == 'Paste and place.'
    assert setup['smt'].explanation_video_loop


@pytest.mark.django_db
def test_edit_page_rejects_a_bad_icon_name(client, setup):
    client.force_login(setup['staff'])
    response = client.post(reverse('erp:production_stage_edit', args=[setup['smt'].pk]),
                           _edit_data(setup['smt'], icon='truck'))
    assert response.status_code == 200
    setup['smt'].refresh_from_db()
    assert setup['smt'].icon == ''


@pytest.mark.django_db
def test_replacing_and_clearing_the_image_removes_old_files(client, setup, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    client.force_login(setup['staff'])
    url = reverse('erp:production_stage_edit', args=[setup['smt'].pk])

    client.post(url, {**_edit_data(setup['smt']), 'explanation_image': SimpleUploadedFile('a.png', png_bytes())})
    setup['smt'].refresh_from_db()
    first = setup['smt'].explanation_image.path
    assert first.startswith(str(tmp_path / 'production_stage_media'))

    client.post(url, {**_edit_data(setup['smt']), 'explanation_image': SimpleUploadedFile('b.png', png_bytes())})
    setup['smt'].refresh_from_db()
    second = setup['smt'].explanation_image.path
    assert not os.path.exists(first)
    assert os.path.exists(second)

    client.post(url, {**_edit_data(setup['smt']), 'explanation_image-clear': 'on'})
    setup['smt'].refresh_from_db()
    assert not setup['smt'].explanation_image
    assert not os.path.exists(second)


@pytest.mark.django_db
def test_any_logged_in_user_can_get_a_stage_image(client, setup, settings, tmp_path, django_user_model):
    settings.MEDIA_ROOT = str(tmp_path)
    setup['smt'].explanation_image.save('smt.png', ContentFile(png_bytes()), save=True)
    name = setup['smt'].explanation_image.name
    no_org_user = django_user_model.objects.create_user(email='noorg@example.com', password='x')

    client.force_login(no_org_user)
    assert client.get(reverse('media', args=[name])).status_code == 200


@pytest.mark.django_db
def test_other_files_under_stage_media_are_not_served(client, setup, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    stray = tmp_path / 'production_stage_media' / '99'
    stray.mkdir(parents=True)
    (stray / 'stray.png').write_bytes(png_bytes())

    client.force_login(setup['member'])
    assert client.get(reverse('media', args=['production_stage_media/99/stray.png'])).status_code == 404


@pytest.mark.django_db
def test_anonymous_cannot_get_a_stage_image(client, setup, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    setup['smt'].explanation_image.save('smt.png', ContentFile(png_bytes()), save=True)
    response = client.get(reverse('media', args=[setup['smt'].explanation_image.name]))
    assert response.status_code == 302


# --- Migration 0053: link existing batch stages by name ---

@pytest.mark.django_db(transaction=True)
def test_migration_links_batch_stages_by_name_and_keeps_unmatched_ones():
    executor = MigrationExecutor(connection)
    # Roll back only erp; every other app stays at its latest migration.
    targets = [node for node in executor.loader.graph.leaf_nodes() if node[0] != 'erp']
    targets.append(('erp', '0052_productionstage_explainer_and_batch_link'))
    executor.migrate(targets)
    old_apps = executor.loader.project_state(targets).apps

    OldOrg = old_apps.get_model('crm', 'Org')
    OldDesign = old_apps.get_model('device', 'Design')
    OldBatch = old_apps.get_model('erp', 'Batch')
    OldStage = old_apps.get_model('erp', 'ProductionStage')
    OldBatchStage = old_apps.get_model('erp', 'BatchProductionStage')

    org = OldOrg.objects.create(company_name='Migration Org')
    design = OldDesign.objects.create(client=org, sku='MIG', name='Migration', hw_version='1.0')
    batch = OldBatch.objects.create(design=design, quantity=1)
    testing = OldStage.objects.create(name='Testing', color='#00ff11', order=1)
    OldBatchStage.objects.create(batch=batch, name='Testing', color='#00ff11', order=1)
    OldBatchStage.objects.create(batch=batch, name='Hand Wash', color='#123456', order=2)

    try:
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([('erp', '0054_batchproductionstage_drop_copied_fields')])

        stages = list(BatchProductionStage.objects.filter(batch_id=batch.pk).select_related('production_stage'))
        assert stages[0].production_stage_id == testing.pk
        recreated = stages[1].production_stage
        assert (recreated.name, recreated.color, recreated.active) == ('Hand Wash', '#123456', False)
    finally:
        call_command('migrate', verbosity=0)
