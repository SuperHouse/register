from crm.models import Org
from crm.schema import ClientSchema
from device.api import router


@router.get('clients/', response=list[ClientSchema])
def get_clients(request):
    return Org.objects.all()
