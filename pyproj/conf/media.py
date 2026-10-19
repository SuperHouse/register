"""
Serve uploaded media files with the same access rules as the pages that show them.

Every file under MEDIA_ROOT belongs to a record (a DesignAsset, a DeviceImage, an
Org's logo, ...). This view finds the record by the file name stored in the
database and checks that the user may see it. Staff may see everything. Any other
user may only see files that belong to their own Org(s), and never an asset marked
internal. Files with no matching rule are staff only.

Forbidden and missing files both give a 404, so the response doesn't tell anyone
that a file exists. Anonymous users never get here: LoginRequiredMiddleware sends
them to the login page first.
"""

import mimetypes
import os
import posixpath

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.http import FileResponse, Http404, HttpResponseNotModified
from django.utils._os import safe_join
from django.utils.http import http_date
from django.views.static import was_modified_since
from easy_thumbnails.models import Thumbnail

from crm.models import Org
from device.models import DesignAsset, DeviceAsset, DeviceImage, TestImage

# Types that are safe to show inline in the browser. Anything else (HTML, SVG, ...)
# is sent as a download, so an uploaded file can't run script on this site's origin.
INLINE_CONTENT_TYPES = {
    'image/png',
    'image/jpeg',
    'image/gif',
    'image/webp',
    'image/bmp',
    'application/pdf',
}


def _design_asset_allowed(user, name):
    return DesignAsset.objects.filter(file=name, internal=False, design__client__users=user).exists()


def _device_asset_allowed(user, name):
    return DeviceAsset.objects.filter(file=name, internal=False, device__design__client__users=user).exists()


def _device_image_allowed(user, name):
    return DeviceImage.objects.filter(image=name, device__design__client__users=user).exists()


def _test_image_allowed(user, name):
    return TestImage.objects.filter(image=name, test_record__device__design__client__users=user).exists()


def _org_logo_allowed(user, name):
    return Org.objects.filter(logo=name, users=user).exists()


def _thumbnail_allowed(user, name):
    # easy_thumbnails records each thumbnail it generates, with a link to its source
    # file. A thumbnail has the same access rule as the file it was made from.
    source_names = Thumbnail.objects.filter(name=name).values_list('source__name', flat=True)
    return any(
        not source_name.startswith(settings.THUMBNAIL_BASEDIR + '/') and user_can_access_media(user, source_name)
        for source_name in source_names
    )


# Upload-path prefix -> rule for non-staff users. A prefix not listed here is staff only
# (part images/assets, test step assets/diagnostic images, and anything unexpected).
NON_STAFF_RULES = {
    'design_assets/': _design_asset_allowed,
    'device_assets/': _device_asset_allowed,
    'device_images/': _device_image_allowed,
    'test_images/': _test_image_allowed,
    'clients/': _org_logo_allowed,
    settings.THUMBNAIL_BASEDIR + '/': _thumbnail_allowed,
}


def user_can_access_media(user, name):
    """Can `user` see the media file stored as `name` (a path relative to MEDIA_ROOT)?"""
    if not user.is_authenticated or not user.is_active:
        return False
    if user.is_staff:
        return True
    for prefix, rule in NON_STAFF_RULES.items():
        if name.startswith(prefix):
            return rule(user, name)
    return False


def serve_media(request, path):
    name = posixpath.normpath(path).lstrip('/')
    try:
        fullpath = safe_join(settings.MEDIA_ROOT, name)
    except SuspiciousFileOperation:
        raise Http404
    if not os.path.isfile(fullpath) or not user_can_access_media(request.user, name):
        raise Http404

    statobj = os.stat(fullpath)
    if not was_modified_since(request.META.get('HTTP_IF_MODIFIED_SINCE'), statobj.st_mtime):
        return HttpResponseNotModified()

    content_type, encoding = mimetypes.guess_type(fullpath)
    if encoding or not content_type:
        # e.g. a .tar.gz: send the bytes as they are, as a plain download.
        content_type = 'application/octet-stream'
    response = FileResponse(
        open(fullpath, 'rb'),
        content_type=content_type,
        as_attachment=content_type not in INLINE_CONTENT_TYPES,
        filename=os.path.basename(fullpath),
    )
    response['Last-Modified'] = http_date(statobj.st_mtime)
    response['Cache-Control'] = 'private'
    return response
