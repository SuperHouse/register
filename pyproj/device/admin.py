from easy_thumbnails.files import get_thumbnailer

from django.contrib import admin
from django.utils.html import format_html

from .models import Client, Design, Device, DeviceEvent, TestImage, TestRecord


class DesignAdmin(admin.ModelAdmin):
    fields = ['client', ('sku', 'hw_version'), 'name', 'description', 'price', 'price2']
    list_filter = ['client', 'sku']
    search_fields = ['sku', 'name', 'hw_version']


class TestRecordInline(admin.StackedInline):
    model = TestRecord
    extra = 0


class DeviceEventInline(admin.StackedInline):
    model = DeviceEvent
    extra = 0


class DeviceAdmin(admin.ModelAdmin):
    autocomplete_fields = ['design']
    inlines = [TestRecordInline, DeviceEventInline]


class TestImageAdmin(admin.ModelAdmin):
    list_display = ['test_record', 'image', 'thumbnail']
    list_filter = ['test_record']
    readonly_fields = ['thumbnail']

    def thumbnail(self, obj):
        thumb_url = get_thumbnailer(obj.image)['testimage-admin-thumbs'].url
        return format_html(f'<img src="{thumb_url}" />')

    thumbnail.short_description = 'thumbnail'


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
admin.site.register(DeviceEvent)
admin.site.register(TestImage, TestImageAdmin)
admin.site.register(TestRecord, TestRecordAdmin)

admin.site.site_header = 'Device register'
admin.site.site_title = 'SuperHouse device register'
admin.site.site_url = '/device/'  # reverse() doesn't work here
