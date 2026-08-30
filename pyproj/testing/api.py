# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
"""Test Suite Package API endpoints (issue #116), staff-only. A TestSuite's own pk is already a
definitive identifier for one specific version of a design's Test Suite - see TestSuite in
models.py - it just wasn't exposed anywhere outside the admin until now. These two endpoints
expose it: one to list available Test Suite Packages (optionally scoped to a design), and one to
download a specific package's ZIP archive by that pk, reusing the same
build_test_suite_package_response() the "Download" link on the Design detail page's Test Suite
tab already uses.

Policy (added after issue #116's initial implementation): a Testomatic tester must never see or
fetch a Test Suite Package that's still a DRAFT - only a SAVED (finalised) version is fit for a
tester to run, since a draft can still change underneath it mid-edit. Both endpoints enforce this
by excluding/refusing DRAFT suites; the UI's own Design detail page is unaffected; it still shows
and downloads the draft being edited, same as before - this restriction is API-only."""
from django.shortcuts import get_object_or_404

from api.routes import router
from .models import TestSuite
from .schemas import TestSuiteSchema
from .views import build_test_suite_package_response
from device.schemas import Message


@router.get('test-suites/', response={200: list[TestSuiteSchema], 403: Message})
def list_test_suites(request, design_id: int = None):
    if not request.auth.is_staff:
        return 403, {'message': 'API key does not have access to Test Suite Packages'}

    suites = TestSuite.objects.exclude(status=TestSuite.DRAFT)
    if design_id is not None:
        suites = suites.filter(design_id=design_id)

    return suites


@router.get('test-suites/{suite_id}/download/', response={403: Message})
def download_test_suite(request, suite_id: int):
    if not request.auth.is_staff:
        return 403, {'message': 'API key does not have access to Test Suite Packages'}

    suite = get_object_or_404(TestSuite, pk=suite_id)
    if suite.status == TestSuite.DRAFT:
        return 403, {'message': 'Test Suite Package is still a draft and is not available for download'}

    return build_test_suite_package_response(suite)
