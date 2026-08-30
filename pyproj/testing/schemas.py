# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from datetime import datetime
from typing import Literal

from ninja import Schema


class TestSuiteSchema(Schema):
    id: int
    design_id: int
    version: int
    status: Literal['DRAFT', 'SAVED']
    created_dt: datetime
