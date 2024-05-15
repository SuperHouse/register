from django.contrib import admin

from .models import Client, Design, Device, TestImage, TestRecord


class DesignAdmin(admin.ModelAdmin):
    fields = ['client', 'sku', ('name', 'hw_version'), 'description']
    list_filter = ['client', 'sku']
    search_fields = ['sku', 'name', 'hw_version']


class TestRecordInline(admin.StackedInline):
    model = TestRecord
    extra = 0


class DeviceAdmin(admin.ModelAdmin):
    autocomplete_fields = ['design']
    inlines = [TestRecordInline]


class TestImageInline(admin.TabularInline):
    model = TestImage
    extra = 0


class TestRecordAdmin(admin.ModelAdmin):
    inlines = [TestImageInline]


class TestRecordAdmin(admin.ModelAdmin):
    inlines = [TestImageInline]


admin.site.register(Client)
admin.site.register(Design, DesignAdmin)
admin.site.register(Device, DeviceAdmin)
admin.site.register(TestImage)
admin.site.register(TestRecord, TestRecordAdmin)

admin.site.site_header = 'Device register'
admin.site.site_title = 'SuperHouse device register'
admin.site.site_url = '/device/'  # reverse() doesn't work here
