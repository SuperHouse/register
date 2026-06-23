from django.db import migrations


def copy_api_keys_to_users(apps, schema_editor):
    Org = apps.get_model('crm', 'Org')
    for org in Org.objects.exclude(api_key__isnull=True).exclude(api_key=''):
        user = org.users.filter(api_key__isnull=True).first()
        if user:
            user.api_key = org.api_key
            user.save(update_fields=['api_key'])


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0003_rename_client_org'),
        ('crm', '0004_copy_clients_from_device'),
        ('authuser', '0005_user_api_key'),
    ]

    operations = [
        migrations.RunPython(copy_api_keys_to_users, reverse_noop),
    ]
