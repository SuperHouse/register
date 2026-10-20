from crm.views.branding import branded_host_add, branded_host_edit, branded_host_delete, favicon
from crm.views.organisations import organisation_list, organisation_detail, organisation_edit
from crm.views.users import user_list, user_add, user_edit, user_regenerate_key

__all__ = [
    'branded_host_add',
    'branded_host_edit',
    'branded_host_delete',
    'favicon',
    'organisation_list',
    'organisation_detail',
    'organisation_edit',
    'user_list',
    'user_add',
    'user_edit',
    'user_regenerate_key',
]
