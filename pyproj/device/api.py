import ipaddress
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import File, Form, Router, UploadedFile
from ninja.security import APIKeyHeader

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

# Browser-based API explorer: http://localhost:8000/api/v1/docs
# (Doesn't need an API key, but you'll need to be logged in)


class AuthByApiKey(APIKeyHeader):
    param_name = 'X-API-Key'

    # https://stackoverflow.com/questions/4581789/how-do-i-get-user-ip-address-in-django
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def authenticate(self, request, key):
        request_from = self.get_client_ip(request)
        ip_addr = ipaddress.ip_address(request_from)

        if settings.API_ALLOW_IPV4_SUBNET:
            allowed_ipv4_network = ipaddress.ip_network(settings.API_ALLOW_IPV4_SUBNET)
            if ip_addr not in allowed_ipv4_network:
                return

        if key and Client.objects.filter(api_key=key).exists():
            return key


header_key_auth = AuthByApiKey()
router = Router(auth=header_key_auth)


@router.get('test-endpoint-noauth/', auth=None, response=Message)
def endpoint_test_noauth(request):
    return {'message': 'Success.'}


@router.get('test-endpoint/', response=Message)
def endpoint_test_withauth(request):
    return {'message': 'Success.'}


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
