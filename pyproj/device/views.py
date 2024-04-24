from django.shortcuts import render

from .models import Client

def top(request):
    clients = Client.objects.all()

    context = {
        'clients': clients,
    }

    return render(request, 'device/top.html', context)


def general_action(request):
    return render(request, 'device/general_action.html')


def device_detail(request, device_number):
    device = None

    context = {
        'device': device,
    }

    return render(request, 'device/device_detail.html', context)


