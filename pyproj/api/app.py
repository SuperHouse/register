from django.contrib.admin.views.decorators import staff_member_required
from ninja import NinjaAPI, Router


"""
API builtin OAS/swagger docs (@staff_member_required):
http://localhost:8000/api/v1/docs
"""


api = NinjaAPI(docs_decorator=staff_member_required)



