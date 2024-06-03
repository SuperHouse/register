from django.contrib import messages
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import DatabaseError, IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone

from login_required import login_not_required

from .forms import AddDevicesForm, DeviceEventForm, TestRecordForm
from .models import Client, Design, Device, DeviceEvent, TestRecord


def top(request):
    if request.user.is_staff:
        clients = Client.objects.all()
        designs = Design.objects.all()
        devices = Device.objects.all()
    else:
        clients = Client.objects.filter(users=request.user)
        designs = Design.objects.filter(client__in=clients).all()
        devices = Device.objects.filter(design__client__in=clients).all()

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


def add_devices(request):
    errors = []
    if request.method == "POST":
        form = AddDevicesForm(request.POST, hide_override=False)
        if form.is_valid():
            with transaction.atomic():
                design = form.cleaned_data['design']
                qty = form.cleaned_data['qty']
                first_serial = form.cleaned_data['first_serial']
                assembly_date = form.cleaned_data['assembly_date']

                for i in range(qty):
                    try:
                        Device.objects.create(
                            pk=first_serial + i,
                            design=design,
                            assembly_date=assembly_date,
                        )
                    except IntegrityError as e:
                        errors.append(f"Integrity error occurred: {e}")
                    except ValidationError as e:
                        errors.append(f"Validation error occurred: {e}")
                    except ObjectDoesNotExist as e:
                        errors.append(f"Related object does not exist: {e}")
                    except DatabaseError as e:
                        errors.append(f"General database error occurred: {e}")
                if errors:
                    result = 'Found errors, no changes were saved'
                    transaction.set_rollback(True)

            # redirect to a new URL:
            messages.success(request, f"Added {qty} {design} device{'s' if qty > 1 else ''}")

            return redirect("device:add_devices")
        else:
            messages.warning(
                request,
                "Some field values don't match expected defaults.  Please review, and if the values are correct, click the override before resubmitting.",
            )
            # Drop through to re-render the form with the error messages

    # if a GET (or any other method) we'll create a blank form
    else:
        initial = AddDevicesForm.get_initials()
        form = AddDevicesForm(hide_override=True, initial=initial)

    ctx = {
        'last20': Device.objects.order_by('-pk')[:20],
        'form': form,
        'errors': errors,
    }

    return render(request, "device/add_devices.html", ctx)


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

    return redirect('device:device_detail', device_number=device.pk)


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
    }

    return render(request, "device/test_record_edit.html", ctx)
