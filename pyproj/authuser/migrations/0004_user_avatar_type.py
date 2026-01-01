# Generated migration for avatar_type field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authuser', '0003_add_superhouse_site'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='avatar_type',
            field=models.CharField(
                choices=[('initials', 'Initials'), ('gravatar', 'Gravatar')],
                default='initials',
                help_text='Choose how your profile picture is displayed',
                max_length=20
            ),
        ),
    ]

