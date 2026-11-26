# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django.db import IntegrityError, models, transaction
from django.utils import timezone

from crm.models import Org
from device.models import Design


class Project(models.Model):
    """A piece of client work, from enquiry through R&D to handover to production (register#159).

    `phase` is where the work is; `status` is whether it is moving. They are separate so that a
    project can be "on hold during Prototyping" and still show where it stopped.
    """

    ENQUIRY = 'ENQUIRY'
    QUOTING = 'QUOTING'
    QUOTED = 'QUOTED'
    DESIGN = 'DESIGN'
    PROTOTYPING = 'PROTOTYPING'
    PRE_PRODUCTION = 'PRE_PRODUCTION'
    PRODUCTION = 'PRODUCTION'
    PHASE_CHOICES = [
        (ENQUIRY, 'Enquiry'),
        (QUOTING, 'Quoting'),
        (QUOTED, 'Quoted'),
        (DESIGN, 'Design'),
        (PROTOTYPING, 'Prototyping'),
        (PRE_PRODUCTION, 'Pre-production'),
        (PRODUCTION, 'Production'),
    ]

    ACTIVE = 'ACTIVE'
    ON_HOLD = 'ON_HOLD'
    CLOSED = 'CLOSED'
    DECLINED = 'DECLINED'
    STATUS_CHOICES = [
        (ACTIVE, 'Active'),
        (ON_HOLD, 'On hold'),
        (CLOSED, 'Closed'),
        (DECLINED, 'Declined'),
    ]

    code = models.CharField(
        max_length=20, unique=True, editable=False,
        help_text='Set automatically when the project is created, e.g. P-2026-014.',
    )
    org = models.ForeignKey(Org, on_delete=models.PROTECT, related_name='projects', verbose_name='Organisation')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    phase = models.CharField(max_length=20, choices=PHASE_CHOICES, default=ENQUIRY)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=ACTIVE)
    start_date = models.DateField(null=True, blank=True)
    target_date = models.DateField(null=True, blank=True)
    designs = models.ManyToManyField(Design, blank=True, related_name='projects')
    created_dt = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ['-created_dt']

    def __str__(self):
        return f'{self.code}: {self.name}'

    @staticmethod
    def next_code(year):
        """Return the next free code for `year`, e.g. P-2026-014. Numbering restarts each year."""
        prefix = f'P-{year}-'
        numbers = [
            int(code[len(prefix):])
            for code in Project.objects.filter(code__startswith=prefix).values_list('code', flat=True)
            if code[len(prefix):].isdigit()
        ]
        return f'{prefix}{max(numbers, default=0) + 1:03d}'

    def save(self, *args, **kwargs):
        if self.code:
            return super().save(*args, **kwargs)
        # Two projects created at the same moment could pick the same code; the unique
        # constraint rejects the second, so try again with the next number.
        year = timezone.localtime(self.created_dt).year
        for attempt in range(5):
            self.code = self.next_code(year)
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                if attempt == 4:
                    raise
