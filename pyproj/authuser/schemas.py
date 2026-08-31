# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from ninja import Schema


class VerifyOperatorSchema(Schema):
    email: str
    password: str


class OperatorProfileSchema(Schema):
    id: int
    email: str
    full_name: str
    avatar_type: str
    is_staff: bool
