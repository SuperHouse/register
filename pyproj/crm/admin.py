from django.contrib import admin

from crm.models import BrandedHost, Org

admin.site.register(Org)


@admin.register(BrandedHost)
class BrandedHostAdmin(admin.ModelAdmin):
    list_display = ['hostname', 'org', 'display_name', 'sidebar_colour', 'accent_colour']
    list_select_related = ['org']
    search_fields = ['hostname', 'display_name', 'org__company_name']
