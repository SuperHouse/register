from django.shortcuts import render

# Create your views here.
def top(request):
    devices = []

    context = {
        'devices': devices,
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


