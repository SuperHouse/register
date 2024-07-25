from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from login_required import login_not_required

from .forms import DeviceEventForm, TestRecordForm
from .models import Client, Design, Device, DeviceEvent, TestRecord


def top(request):
    clients = Client.objects.all()
    designs = Design.objects.prefetch_related("client").all()
    devices = Device.objects.prefetch_related("design").order_by('pk').all()
    if not request.user.is_staff:
        clients = clients.filter(users=request.user)
        designs = designs.filter(client__in=clients)
        devices = devices.filter(design__client__in=clients)

    context = {
        'clients': clients,
        'designs': designs,
        'devices': devices,
    }

    return render(request, 'device/top.html', context)


@login_not_required
def perm_report(request):
    return render(request, 'device/perm_report.html')


def general_action(request):
    return render(request, 'device/general_action.html')


@staff_member_required
def device_grid(request):
    # FIXME: Very slow to run, so the user has to agree first that
    # they know it's going to be slow.  The slowdown isn't in the db.
    # FIXME: Doesn't show device events.
    # FIXME: Fix Frappe-datatable layout problem in second tab.
    def provide1():
        for device in (
            Device.objects.select_related('design').prefetch_related('testrecord_set').all()
        ):  # .select_related("testrecord_set")
            tr_set = device.testrecord_set.all()
            if tr_set:
                if tr_set.count() > 1:
                    tr_str = ', '.join([tr.get_test_dt_as_string() for tr in tr_set])
                    tr_str = f'({tr_str})'
                else:
                    tr_str = tr_set.first().get_test_dt_as_string()
            else:
                tr_str = ''

            row = (
                device.pk,
                device.design_id,
                device.assembly_date,
                tr_str,
                device.sw_version or '',
                device.notes or '',
                device.design.name,
                device.design.hw_version,
                device.invoice or '',
            )

            yield row

    def provide2():
        for design in Design.objects.all():
            row = (
                design.pk,
                design.client.pk,
                design.sku,
                design.name,
                design.hw_version,
                design.client.company_name,
                design.price or '',
                design.price2 or '',
            )

            yield row

    context = {
        'warned': False,
    }

    if request.GET.get('warned'):
        context.update(
            {
                'warned': True,
                'headings1': 'Serial/DeviceTypeSerial/Assembled/Tested/Firmware/Notes/Device/HW Version/Invoice'.split(
                    '/'
                ),
                'data1': provide1(),
                'headings2': 'Serial/ClientSerial/SKU/Name/HW Version/Customer/Price/Price2'.split('/'),
                'data2': provide2(),
            }
        )

    return render(request, 'device/device_grid.html', context)


def device_detail(request, device_number):
    if request.user.is_staff:
        device = get_object_or_404(Device, pk=device_number)
    else:
        clients = Client.objects.filter(users=request.user)
        device = get_object_or_404(Device, design__client__in=clients, pk=device_number)

    context = {
        'device': device,
    }

    return render(request, 'device/device_detail.html', context)


def device_action(request, device_number):
    if request.user.is_staff:
        device = get_object_or_404(Device, pk=device_number)
    else:
        clients = Client.objects.filter(users=request.user)
        device = get_object_or_404(Device, design__client__in=clients, pk=device_number)

    context = {
        'device': device,
    }

    messages.success(request, 'Action worked just fine!')

    return render(request, 'device/device_action.html', context)


def device_search(request):
    q = request.GET.get('q') or ''

    if q:
        try:
            # FIXME: Try doing this with a .get().
            device_set = Device.objects.filter(pk=q)
            if device_set:
                # Ok we found something...
                if not request.user.is_staff:
                    clients = Client.objects.filter(users=request.user)
                    device_set = device_set.filter(design__client__in=clients)
                if device_set:
                    device = device_set.first()
                    return redirect("device:device_detail", device_number=device.pk)
        except Device.DoesNotExist:
            pass

    if q:
        # If there was a search query, but we found something, we would have redirected.
        messages.error(request, "There's no board with that serial number.")

    context = {
        'q': q,
    }

    return render(request, 'device/device_search.html', context)


def device_event_add(request, device_number):
    if request.user.is_staff:
        device = get_object_or_404(Device, pk=device_number)
    else:
        clients = Client.objects.filter(users=request.user)
        device = get_object_or_404(Device, design__client__in=clients, pk=device_number)

    if request.method == "POST":
        form = DeviceEventForm(request.POST, initial={'device': device})
        if form.is_valid():
            form.instance.device = device
            event = form.save()

            messages.success(request, 'Event added.')

            return redirect("device:device_detail", device_number=event.device.pk)
        else:
            messages.warning(
                request,
                "Some field values have errors.  Please review, and amend as required.",
            )
            # Drop through to re-render the form with the error messages

    else:
        # if a GET (or any other method) we'll create a blank form
        form = DeviceEventForm()

    ctx = {
        'form': form,
        'device': device,
        'operation': 'Add',
        'ts': None,
    }

    return render(request, "device/device_event_edit.html", ctx)


def device_event_edit(request, device_event_number):
    if request.user.is_staff:
        event = get_object_or_404(DeviceEvent, pk=device_event_number)
    else:
        clients = Client.objects.filter(users=request.user)
        event = get_object_or_404(DeviceEvent, device__design__client__in=clients, pk=device_event_number)

    if request.method == "POST":
        form = DeviceEventForm(request.POST, instance=event)
        if form.is_valid():
            form.instance.event_dt = timezone.now()
            event = form.save()

            messages.success(request, 'Event saved.')

            return redirect("device:device_detail", device_number=event.device.pk)
        else:
            messages.warning(
                request,
                "Some field values have errors.  Please review, and amend as required.",
            )
            # Drop through to re-render the form with the error messages

    else:
        # if a GET (or any other method) we'll create a blank form
        form = DeviceEventForm(instance=event)

    ctx = {
        'form': form,
        'device': event.device,
        'operation': 'Edit',
        'ts': event.event_dt,
    }

    return render(request, "device/device_event_edit.html", ctx)


def device_event_delete(request, device_event_number):
    if request.user.is_staff:
        event = get_object_or_404(DeviceEvent, pk=device_event_number)
    else:
        clients = Client.objects.filter(users=request.user)
        event = get_object_or_404(DeviceEvent, device__design__client__in=clients, pk=device_event_number)

    if request.method == "POST":
        event.delete()
        messages.success(
            request,
            "Device event deleted.",
        )

        return redirect("device:device_detail", device_number=event.device.pk)

    ctx = {
        'event': event,
    }

    return render(request, "device/device_event_delete.html", ctx)


def test_record_add(request, device_number):
    if request.user.is_staff:
        device = get_object_or_404(Device, pk=device_number)
    else:
        clients = Client.objects.filter(users=request.user)
        device = get_object_or_404(Device, design__client__in=clients, pk=device_number)

    if request.method == "POST":
        form = TestRecordForm(request.POST, initial={'device': device})
        if form.is_valid():
            form.instance.device = device
            event = form.save()

            messages.success(request, 'Test record added.')

            return redirect("device:device_detail", device_number=event.device.pk)
        else:
            messages.warning(
                request,
                "Some field values have errors.  Please review, and amend as required.",
            )
            # Drop through to re-render the form with the error messages

    else:
        # if a GET (or any other method) we'll create a blank form
        form = TestRecordForm()

    ctx = {
        'form': form,
        'device': device,
        'operation': 'Add',
        'ts': None,
    }

    return render(request, "device/device_event_edit.html", ctx)


def test_record_edit(request, test_record_number):
    if request.user.is_staff:
        test_record = get_object_or_404(TestRecord, pk=test_record_number)
    else:
        clients = Client.objects.filter(users=request.user)
        test_record = get_object_or_404(TestRecord, device__design__client__in=clients, pk=test_record_number)

    if request.method == "POST":
        form = TestRecordForm(request.POST, instance=test_record)
        if form.is_valid():
            form.save()

            messages.success(request, 'Test record saved.')

            return redirect("device:device_detail", device_number=test_record.device.pk)
        else:
            messages.warning(
                request,
                "Some field values have errors.  Please review, and amend as required.",
            )
            # Drop through to re-render the form with the error messages

    else:
        # if a GET (or any other method) we'll create a blank form
        form = TestRecordForm(instance=test_record)

    ctx = {
        'form': form,
        'device': test_record.device,
        'operation': 'Edit',
        'ts': test_record.test_dt,
    }

    return render(request, "device/test_record_edit.html", ctx)
