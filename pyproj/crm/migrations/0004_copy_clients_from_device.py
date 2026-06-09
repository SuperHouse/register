from django.db import migrations


def copy_clients_from_device(apps, schema_editor):
    cursor = schema_editor.connection.cursor()

    cursor.execute("SELECT id, company_name, logo, api_key FROM device_client")
    clients = cursor.fetchall()
    for client_id, company_name, logo, api_key in clients:
        cursor.execute(
            "INSERT INTO crm_client (id, company_name, logo, api_key, is_client, is_manufacturer, is_supplier)"
            " VALUES (%s, %s, %s, %s, 1, 0, 0)",
            [client_id, company_name, logo or "", api_key],
        )

    cursor.execute("SELECT client_id, user_id FROM device_client_users")
    for client_id, user_id in cursor.fetchall():
        cursor.execute(
            "INSERT INTO crm_client_users (client_id, user_id) VALUES (%s, %s)",
            [client_id, user_id],
        )

    if clients:
        max_id = max(c[0] for c in clients)
        cursor.execute(
            "INSERT OR REPLACE INTO sqlite_sequence (name, seq) VALUES ('crm_client', %s)",
            [max_id],
        )


def reverse_copy(apps, schema_editor):
    cursor = schema_editor.connection.cursor()
    cursor.execute("DELETE FROM crm_client_users")
    cursor.execute("DELETE FROM crm_client")


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0002_client_is_client_client_is_manufacturer_and_more"),
        ("device", "0030_add_device_asset"),
    ]

    operations = [
        migrations.RunPython(copy_clients_from_device, reverse_copy),
    ]
