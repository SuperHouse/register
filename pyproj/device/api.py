# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
import re
from datetime import datetime

from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import File, Form, UploadedFile

from api.auth import session_or_api_key_auth
from api.routes import router
from crm.models import Org
from device.models import Design, Device, DeviceEvent, DeviceImage, TestImage, TestRecord
from erp.models import Part
from .schemas import (
    DashboardStatsSchema,
    DesignSchema,
    DeviceCreateSchema,
    DeviceImageFormSchema,
    DeviceImageResponseSchema,
    DeviceProgramSchema,
    ExistingDeviceResponseSchema,
    Message,
    TestImageResponseSchema,
    TestRecordResponseSchema,
    TestRecordSchema,
)


def _user_can_access_design(user, design):
    """Whether an API user is allowed to read/write data under the given design's org."""
    return user.is_staff or design.client.users.filter(pk=user.pk).exists()


def _user_can_access_device(user, device):
    """Whether an API user is allowed to read/write data on the given device."""
    return _user_can_access_design(user, device.design)


@router.get('test-endpoint-noauth/', auth=None, response=Message)
def endpoint_test_noauth(request):
    return {'message': 'Success.'}


@router.get('test-endpoint/', response=Message)
def endpoint_test_withauth(request):
    return {'message': 'Success.'}


@router.get('designs/', response=list[DesignSchema])
def get_designs(request, client_pk: int = None):
    ret = Design.objects.order_by("sku", "-hw_version").all()
    if not request.auth.is_staff:
        ret = ret.filter(client__in=Org.objects.filter(users=request.auth))
    if client_pk:
        ret = ret.filter(client__pk=client_pk)

    return ret


@router.post('device/add/', response={200: Message, 201: Message, 400: Message, 403: Message})
def add_or_update_device(request, data: DeviceCreateSchema):
    # Whether the device already exists or not, the design has to be valid
    try:
        design = Design.objects.get(pk=data.design_pk)
    except Design.DoesNotExist:
        return 400, {'message': 'Design not found'}

    if not _user_can_access_design(request.auth, design):
        return 403, {'message': 'API key does not have access to this design'}

    creation_dt = data.creation_dt or timezone.now()

    try:
        device = Device.objects.get(pk=data.pk)
        if not _user_can_access_device(request.auth, device):
            return 403, {'message': 'API key does not have access to this device'}
        # Device exists, so update the design and creation date
        device.design = design
        device.creation_dt = creation_dt
        device.save()

        return 200, {'message': 'Ok'}
    except Device.DoesNotExist:
        device = Device(pk=data.pk, design=design, creation_dt=creation_dt)
        device.save()

        return 201, {'message': 'Created'}


@router.get('device/{device_pk}/', response={200: ExistingDeviceResponseSchema, 403: Message})
def get_existing_device(request, device_pk: str):
    device = get_object_or_404(Device, pk=device_pk)
    if not _user_can_access_device(request.auth, device):
        return 403, {'message': 'API key does not have access to this device'}

    ret = {
        'design_pk': device.design.pk,
        'creation_dt': device.creation_dt,
    }

    return ret


@router.post('device/{device_pk}/program/', response={200: Message, 403: Message})
def post_device_program(request, device_pk: str, data: DeviceProgramSchema):
    device = get_object_or_404(Device, pk=device_pk)
    if not _user_can_access_device(request.auth, device):
        return 403, {'message': 'API key does not have access to this device'}

    new_de = DeviceEvent(device=device, event_type='SW_VERSION', description=data.sw_version)
    new_de.save()

    return {'message': 'Ok'}


@router.post('device/{device_pk}/add-tr/', response={200: TestRecordResponseSchema, 400: Message, 403: Message})
def add_test_record(request, device_pk: str, data: TestRecordSchema):
    if data.result not in [r[0] for r in TestRecord.RESULT_CHOICES]:
        return 400, {'message': 'Invalid value for result'}
    device = get_object_or_404(Device, pk=device_pk)
    if not _user_can_access_device(request.auth, device):
        return 403, {'message': 'API key does not have access to this device'}

    new_tr = TestRecord(device=device, **data.__dict__)
    new_tr.save()

    return {'pk': new_tr.pk}


@router.post('device/{testrecord_pk}/add-image/', response={200: TestImageResponseSchema, 403: Message})
def add_test_image(request, testrecord_pk: str, file: File[UploadedFile]):
    # Note if we ever need to pass in data (which we don't at present):  It has to
    # be done as a form, because the content type is multipart/form-data instead
    # of application/json.  Leaving this here for that future time:
    # def add_test_image(request, testrecord_pk: str, data: Form[TestImageSchema], file: File[UploadedFile]):
    tr = get_object_or_404(TestRecord, pk=testrecord_pk)
    if not _user_can_access_device(request.auth, tr.device):
        return 403, {'message': 'API key does not have access to this device'}

    ti = TestImage(test_record=tr, image=file)
    ti.save()

    return {'thumbnail': ti.image.url}


@router.post('device/{device_pk}/add-device-image/', response={200: DeviceImageResponseSchema, 403: Message, 404: Message})
def add_device_image(request, device_pk: str, data: Form[DeviceImageFormSchema], file: File[UploadedFile]):
    """
    Upload a device image. The API key must belong to the client associated with the device.
    The image datetime can be extracted from the filename if it matches the pattern:
    id-YYYY-MM-DD_h-m-s (e.g., "123-2024-01-15_14-30-45")
    """
    user = request.auth
    device = get_object_or_404(Device, pk=device_pk)

    if not _user_can_access_device(user, device):
        return 403, {'message': 'API key does not have access to this device'}
    
    # Extract datetime from filename if it matches the pattern
    # Pattern: id-YYYY-MM-DD_h_m_s (e.g., "123-2024-01-15_14-30-45")
    filename_dt = None
    if file.name:
        filename = file.name
        # Extract just the filename without path (in case it has one)
        if '/' in filename or '\\' in filename:
            filename = filename.replace('\\', '/').split('/')[-1]
        # Remove file extension
        name_without_ext = filename.rsplit('.', 1)[0] if '.' in filename else filename
        
        # Pattern: id-YYYY-MM-DD_h_m_s
        pattern = r'^.+?-(\d{4})-(\d{2})-(\d{2})_(\d{1,2})-(\d{1,2})-(\d{1,2})$'
        match = re.match(pattern, name_without_ext)
        
        if match:
            try:
                year = int(match.group(1))
                month = int(match.group(2))
                day = int(match.group(3))
                hour = int(match.group(4))
                minute = int(match.group(5))
                second = int(match.group(6))
                
                # Validate the date/time values
                if (1 <= month <= 12 and 1 <= day <= 31 and 
                    0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
                    # Create datetime object
                    parsed_dt = datetime(year, month, day, hour, minute, second)
                    # Make it timezone-aware using the current timezone
                    if timezone.is_naive(parsed_dt):
                        parsed_dt = timezone.make_aware(parsed_dt)
                    filename_dt = parsed_dt
            except (ValueError, TypeError):
                # If parsing fails, filename_dt remains None
                pass
    
    # Create the DeviceImage
    device_image = DeviceImage(
        device=device,
        image=file,
        notes=data.notes,
        image_dt=filename_dt if filename_dt else timezone.now()
    )
    device_image.save()
    
    return {'image_url': device_image.image.url, 'pk': device_image.pk}


@router.get('dashboard-stats/', auth=session_or_api_key_auth, response=DashboardStatsSchema)
def get_dashboard_stats(request):
    """Get dashboard statistics. Available to authenticated users and API keys."""
    auth_info = request.auth
    if not auth_info:
        # This shouldn't happen due to auth, but be explicit
        return 401, {'message': 'Unauthorized'}

    # Both session and API-key auth resolve to a user; scope to their orgs unless staff
    user = auth_info['user']
    clients = Org.objects.all()
    designs = Design.objects.all()
    devices = Device.objects.all()

    if not user.is_staff:
        clients = clients.filter(users=user)
        designs = designs.filter(client__in=clients)
        devices = devices.filter(design__client__in=clients)

    # Calculate devices created per month
    devices_by_month = (
        devices
        .annotate(month=TruncMonth('creation_dt'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )

    # Prepare data for chart
    chart_labels = []
    chart_data = []

    for item in devices_by_month:
        if item['month']:
            month_str = item['month'].strftime('%b %Y')
            chart_labels.append(month_str)
            chart_data.append(item['count'])

    return {
        'client_count': clients.count(),
        'design_count': designs.count(),
        'device_count': devices.count(),
        'part_count': Part.objects.count(),
        'chart_labels': chart_labels,
        'chart_data': chart_data,
    }

