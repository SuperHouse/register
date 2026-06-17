from ninja import Router

from api.app import api
from api.auth import AuthByApiKey

router = Router(auth=AuthByApiKey())

api.add_router("/", router)