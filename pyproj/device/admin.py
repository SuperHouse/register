from django.contrib import admin

from .models import Client, Design, Device, TestImage, TestRecord

admin.site.register(Client)
admin.site.register(Design)
admin.site.register(Device)
admin.site.register(TestImage)
admin.site.register(TestRecord)

admin.site.site_header = 'Device register'
admin.site.site_title = 'SuperHouse device register'
admin.site.site_url = '/device/'  # reverse() doesn't work here
