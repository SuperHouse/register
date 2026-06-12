from crm.models import Org
from views.schema import ClientSchema
from device.views import router


@router.get('clients/', response=list[ClientSchema])
def get_clients(request):
    return Org.objects.all()
