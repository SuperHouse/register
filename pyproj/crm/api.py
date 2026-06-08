from crm.models import Client
from crm.schema import ClientSchema
from device.api import router


@router.get('clients/', response=list[ClientSchema])
def get_clients(request):
    return Client.objects.all()
