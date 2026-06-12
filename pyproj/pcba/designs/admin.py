from django.contrib import admin

from pcba.designs.models import DesignAsset, Design, DesignVersion


class DesignAssetInline(admin.TabularInline):
    model = DesignAsset
    extra = 0
    readonly_fields = ['uploaded_dt']


@admin.register(DesignVersion)
class DesignVersionAdmin(admin.ModelAdmin):
    fields = ['design__client', 'design__sku', 'hw_version', 'design__name', 'description', 'price']
    inlines = [DesignAssetInline]


class DesignVersionInline(admin.TabularInline):
    model = DesignVersion
    extra = 1


@admin.register(Design)
class DesignAdmin(admin.ModelAdmin):
    inlines = [DesignVersionInline]
    search_fields = ['sku', 'name']
    list_filter = ['owner']
