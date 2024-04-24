from django.contrib import admin

from .models import Client

admin.site.register(Client)

admin.site.site_header = 'Device register'
admin.site.site_title = 'SuperHouse device register'
admin.site.site_url = '/device/'  # reverse() doesn't work here
