import pytest
from django.db import IntegrityError

from device.models import Client, Design


@pytest.mark.django_db
def test_no_duplicate_designs():
    client1 = Client(company_name='Client One')
    client1.save()

    # Let's create a 1.0 version of an SKU
    design_z1 = Design(client=client1, sku='SKU', name='Zappatron 1.0', hw_version='1.0')
    design_z1.save()

    # Let's create a version 2.0 of the SKU
    design_z2 = Design(client=client1, sku='SKU', name='Zappatron 2.0', hw_version='2.0')
    design_z2.save()

    # Let's try to create another 1.0 version of the SKU (which should fail)
    another_design_z1 = Design(client=client1, sku='SKU', name='Zappatron 1.0 again!', hw_version='1.0')
    with pytest.raises(IntegrityError) as excinfo:
        another_design_z1.save()
    possible_errors = [
        "UNIQUE constraint failed: device_design.sku, device_design.hw_version",  # SQLite
        "(1062, \"Duplicate entry 'SKU-1.0' for key 'unique_sku_hwversion'\")",  # MySQL
    ]
    assert str(excinfo.value) in possible_errors
