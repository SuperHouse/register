from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.shortcuts import render

from login_required import login_not_required

from .models import Client, Design, Device


def top(request):
    clients = Client.objects.all()
    designs = Design.objects.all()
    devices = Device.objects.all()

    context = {
        'clients': clients,
        'designs': designs,
        'devices': devices,
    }

    return render(request, 'device/top.html', context)


def general_action(request):
    return render(request, 'device/general_action.html')


@login_not_required
def perm_report(request):
    return render(request, 'device/perm_report.html')


def device_detail(request, device_number):
    device = get_object_or_404(Device, pk=device_number)

    context = {
        'device': device,
    }

    return render(request, 'device/device_detail.html', context)


def device_action(request, device_number):
    device = get_object_or_404(Device, pk=device_number)

    context = {
        'device': device,
    }

    messages.success(request, 'Action worked just fine!')

    return render(request, 'device/device_action.html', context)
