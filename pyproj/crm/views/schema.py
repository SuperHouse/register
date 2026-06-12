from ninja import ModelSchema

from crm.models import Org


class ClientSchema(ModelSchema):
    class Meta:
        model = Org
        fields = ('id', 'company_name')
