from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import File, Form, Router, UploadedFile

from device.models import Client, Design, Device, DeviceEvent, TestImage, TestRecord

from .schemas import (
    ClientSchema,
    DesignSchema,
    DeviceCreateSchema,
    DeviceProgramSchema,
    ExistingDeviceResponseSchema,
    Message,
    TestImageResponseSchema,
    TestRecordResponseSchema,
    TestRecordSchema,
)

router = Router()


# FIXME: If we make all these endpoints staff-only, we don't need to check for cross-client access.
@router.get('clients/', response=list[ClientSchema])
def get_clients(request):
    return Client.objects.all()


@router.get('designs/', response=list[DesignSchema])
def get_designs(request, client_pk: int = None):
    ret = Design.objects.order_by("sku", "-hw_version").all()
    if client_pk:
        ret = ret.filter(client__pk=client_pk)

    return ret


@router.post('device/add/', response={200: Message, 201: Message, 400: Message})
def add_or_update_device(request, data: DeviceCreateSchema):
    # Whether the device already exists or not, the design has to be valid
    try:
        design = Design.objects.get(pk=data.design_pk)
    except Design.DoesNotExist:
        return 400, {'message': 'Design not found'}

    creation_dt = data.creation_dt or timezone.now()

    try:
        device = Device.objects.get(pk=data.pk)
        # Device exists, so update the design and creation date
        device.design = design
        device.creation_dt = creation_dt
        device.save()

        return 200, {'message': 'Ok'}
    except Device.DoesNotExist:
        device = Device(pk=data.pk, design=design, creation_dt=creation_dt)
        device.save()

        return 201, {'message': 'Created'}


@router.get('device/{device_pk}/', response=ExistingDeviceResponseSchema)
def get_existing_device(request, device_pk: str):
    device = get_object_or_404(Device, pk=device_pk)
    ret = {
        'design_pk': device.design.pk,
        'creation_dt': device.creation_dt,
    }

    return ret


@router.post('device/{device_pk}/program/', response=Message)
def post_device_program(request, device_pk: str, data: DeviceProgramSchema):
    device = get_object_or_404(Device, pk=device_pk)
    new_de = DeviceEvent(device=device, event_type='SW_VERSION', description=data.sw_version)
    new_de.save()

    return {'message': 'Ok'}


@router.post('device/{device_pk}/add-tr/', response={200: TestRecordResponseSchema, 400: Message})
def add_test_record(request, device_pk: str, data: TestRecordSchema):
    if data.result not in [r[0] for r in TestRecord.RESULT_CHOICES]:
        return 400, {'message': 'Invalid value for result'}
    device = get_object_or_404(Device, pk=device_pk)
    new_tr = TestRecord(device=device, **data.__dict__)
    new_tr.save()

    return {'pk': new_tr.pk}


@router.post('device/{testrecord_pk}/add-image/', response=TestImageResponseSchema)
def add_test_image(request, testrecord_pk: str, file: File[UploadedFile]):
    # Note if we ever need to pass in data (which we don't at present):  It has to
    # be done as a form, because the content type is multipart/form-data instead
    # of application/json.  Leaving this here for that future time:
    # def add_test_image(request, testrecord_pk: str, data: Form[TestImageSchema], file: File[UploadedFile]):
    tr = get_object_or_404(TestRecord, pk=testrecord_pk)
    ti = TestImage(test_record=tr, image=file)
    ti.save()

    return {'thumbnail': ti.image.url}
