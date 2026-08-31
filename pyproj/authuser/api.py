# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
"""Operator credential verification (issue #4 on testomatic-ui) - lets a Testomatic device check
an operator's Register email/password without either party needing to run a browser-based OAuth
flow. Gated by the device's own X-API-Key (the shared router's default auth), same as every
other endpoint - so only a device that already holds valid Register credentials can even attempt
a check. The endpoint itself never leaks whether an email address exists: an unknown email and a
wrong password both come back as the same 401."""
from django.contrib.auth import authenticate

from api.routes import router
from device.schemas import Message
from .schemas import OperatorProfileSchema, VerifyOperatorSchema


@router.post('auth/verify/', response={200: OperatorProfileSchema, 401: Message, 403: Message})
def verify_operator(request, data: VerifyOperatorSchema):
    user = authenticate(request, username=data.email, password=data.password)
    if user is None:
        return 401, {'message': 'Invalid email or password'}
    if not user.is_staff:
        return 403, {'message': 'User is not a staff member'}

    return {
        'id': user.pk,
        'email': user.email,
        'full_name': user.full_name,
        'avatar_type': user.avatar_type,
        'is_staff': user.is_staff,
    }
