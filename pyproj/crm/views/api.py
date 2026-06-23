from api.routes import router
from crm.models import Org
from crm.schema import ClientSchema


@router.get('clients/', response=list[ClientSchema])
def get_clients(request):
    return Org.objects.all()
