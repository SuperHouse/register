from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.shortcuts import render


from .models import Client, Design

def top(request):
    clients = Client.objects.all()
    designs = Design.objects.all()

    context = {
        'clients': clients,
        'designs': designs,
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


