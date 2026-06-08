from ninja import ModelSchema

from crm.models import Client


class ClientSchema(ModelSchema):
    class Meta:
        model = Client
        fields = ('id', 'company_name')
