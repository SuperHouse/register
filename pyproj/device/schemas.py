from datetime import datetime
from typing import Literal
from ninja import ModelSchema, Schema

from crm.schema import ClientSchema
from device.models import Design, TestRecord


class Message(Schema):
    message: str


class DesignSchema(ModelSchema):
    client: ClientSchema

    class Meta:
        model = Design
        fields = ('id', 'sku', 'client', 'name', 'hw_version', 'description')


class ExistingDeviceResponseSchema(Schema):
    design_pk: int
    creation_dt: datetime


class DeviceCreateSchema(Schema):
    pk: int
    design_pk: int
    creation_dt: datetime | None = None


class DeviceProgramSchema(Schema):
    sw_version: str


class TestRecordSchema(ModelSchema):
    result: Literal['NEW', 'PASS', 'FAIL', 'HUH?']

    class Meta:
        model = TestRecord
        fields = ('result', 'test_dt', 'notes')


class TestRecordResponseSchema(Schema):
    pk: int


# Here for later.  We don't use it because we don't pass anything
# but the image, so there's no need for a schema.
class TestImageSchema(Schema):
    pass


class TestImageResponseSchema(Schema):
    thumbnail: str


class DeviceImageFormSchema(Schema):
    notes: str | None = None


class DeviceImageResponseSchema(Schema):
    image_url: str
    pk: int


class DashboardStatsSchema(Schema):
    client_count: int
    design_count: int
    device_count: int
    part_count: int
    chart_labels: list[str]
    chart_data: list[int]


# UserSchema = create_schema(settings.AUTH_USER_MODEL, exclude=['password'])
# UserSchemaUpdate = create_schema(settings.AUTH_USER_MODEL, exclude=['password'], write_only=True)
