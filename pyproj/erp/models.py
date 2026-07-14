# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
import os
import re
from datetime import timedelta

from django.db import models
from django.utils import timezone

from device.models import Design

STALE_REFRESH_THRESHOLD = timedelta(hours=48)


def part_asset_upload_path(instance, filename):
    return f'part_assets/{instance.part_id}/{filename}'


class ProductionStage(models.Model):
    """A stage that a batch can pass through during production (e.g. 'PCBs stocked', 'Top SMT complete')."""
    name = models.CharField(max_length=100, unique=True)
    color = models.CharField(max_length=7, default='#6c757d', help_text='Used to highlight this production stage in the UI')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.name


class ProductionStageTemplate(models.Model):
    """A reusable collection of production stages that can be applied to a batch (e.g. 'Double-sided hi-rel load')."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class ProductionStageTemplateStep(models.Model):
    """A production stage at a particular position within a ProductionStageTemplate."""
    template = models.ForeignKey(ProductionStageTemplate, on_delete=models.CASCADE, related_name='steps')
    production_stage = models.ForeignKey(ProductionStage, on_delete=models.PROTECT)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.template}: {self.order}. {self.production_stage}'


class Batch(models.Model):
    """A production run of a Design, with an ordered list of production operations to perform."""
    design = models.ForeignKey(Design, on_delete=models.PROTECT, related_name='batches')
    po = models.CharField('Purchase order', max_length=50, blank=True)
    quantity = models.PositiveIntegerField()
    notes = models.TextField(null=True, blank=True)
    created_dt = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_dt']

    def __str__(self):
        if self.po:
            return f'{self.design} ({self.po})'
        return f'{self.design} x{self.quantity}'

    @property
    def progress_category(self):
        """Overall progress bucket for the Batches list: 'new', 'in_progress', or 'complete'.

        'complete' means every production stage is Done; 'new' means every stage is
        Not Started (including a batch with no stages at all); anything in between is
        'in_progress'.
        """
        stages = list(self.production_stages.all())
        if stages and all(s.status == BatchProductionStage.DONE for s in stages):
            return 'complete'
        if all(s.status == BatchProductionStage.NOT_STARTED for s in stages):
            return 'new'
        return 'in_progress'


class Location(models.Model):
    """A physical location in a hierarchy (e.g. building > room > shelf)."""
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.CASCADE, related_name='children'
    )
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class Part(models.Model):
    """A component part that can be used in designs."""
    name = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    category = models.ForeignKey(
        'PartCategory', null=True, blank=True, on_delete=models.SET_NULL, related_name='parts'
    )
    device = models.CharField(max_length=200, blank=True, help_text='Component device or part identifier')
    package = models.CharField(max_length=100, blank=True, help_text='Package type (e.g. 0402, SOT-23)')
    value = models.CharField(max_length=100, blank=True, help_text='Component value (e.g. 10k, 100nF)')
    smt_joints = models.PositiveIntegerField(
        null=True, blank=True, help_text='Number of SMT (surface-mount) solder joints for one placement of this part'
    )
    pth_joints = models.PositiveIntegerField(
        null=True, blank=True, help_text='Number of PTH (through-hole) solder joints for one placement of this part'
    )
    fusion_library = models.CharField(max_length=200, blank=True, help_text='Fusion Electronics library name')
    stock = models.IntegerField(
        null=True, blank=True, help_text='Manually-tracked on-hand stock count, independent of supplier listings'
    )
    no_stock_required = models.BooleanField(
        default=False,
        help_text='Part is placed on the BOM but never physically stocked (e.g. test points, DNP parts)'
    )
    image = models.ImageField(upload_to='part_images/', null=True, blank=True)
    created_dt = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['name']

    def __str__(self):
        if self.value:
            return f'{self.name} ({self.value})'
        return self.name

    @property
    def total_stock(self):
        """Sum of stock across all supplier listings, or None if none have a known stock level."""
        known = [source.stock for source in self.sources.all() if source.stock is not None]
        return sum(known) if known else None

    @property
    def has_stale_source_data(self):
        """True if any source listing has stale (or never-refreshed) variant data — see
        PartSource.has_stale_variant_data."""
        return any(source.has_stale_variant_data for source in self.sources.all())

    def cheapest_price_break_for_quantity(self, quantity):
        """The PartPriceBreak, across every known supplier variant, giving the lowest
        per-unit price actually payable when buying `quantity` of this part.

        A break's real minimum purchase quantity is `max(break.quantity, variant.moq)`,
        not just `break.quantity` — a break nominally "at quantity 1" on a variant whose
        MOQ is 2000 (e.g. a full reel) isn't a real per-unit price unless you're buying
        at least 2000 of them, so it can't be used to price a design that only needs a
        handful. For each variant this picks the price at its highest break whose real
        minimum purchase quantity doesn't exceed `quantity` (e.g. breaks at 1/10/100,
        buying 13, uses the 10-break). Breaks genuinely reachable at `quantity` are always
        preferred over ones that aren't, regardless of price, since an unreached break's
        price is only payable by buying more than what's actually needed — only when no
        variant has any break reachable at `quantity` do we fall back to the cheapest
        "smallest lot you can buy" option (each variant's break with the lowest real
        minimum purchase quantity). Returns None if the part has no price break data.
        """
        reached = []
        unreached = []
        for source in self.sources.all():
            for variant in source.variants.all():
                breaks = list(variant.price_breaks.all())
                if not breaks:
                    continue
                moq = variant.moq or 0
                reachable = [b for b in breaks if max(b.quantity, moq) <= quantity]
                if reachable:
                    reached.append(max(reachable, key=lambda b: b.quantity))
                else:
                    unreached.append(min(breaks, key=lambda b: max(b.quantity, moq)))
        candidates = reached or unreached
        return min(candidates, key=lambda b: b.price) if candidates else None


_REFERENCE_SPLIT_RE = re.compile(r'^([A-Za-z]*)(\d*)(.*)$')


class DesignBomEntry(models.Model):
    """A single placed component on a Design's BOM (e.g. RefDes R3 = a 10k resistor Part).

    One row per physical placement, not a collapsed line item with a quantity, so that
    placement data (position/rotation/side) can be attached per-RefDes later for generating
    pick-and-place jobs and AOI targets.
    """
    TOP = 'TOP'
    BOTTOM = 'BOTTOM'
    SIDE_CHOICES = [(TOP, 'Top'), (BOTTOM, 'Bottom')]

    design = models.ForeignKey(Design, on_delete=models.CASCADE, related_name='bom_entries')
    part = models.ForeignKey(Part, on_delete=models.PROTECT, related_name='design_bom_entries')
    reference = models.CharField(max_length=50, help_text='Reference designator (e.g. R3)')
    pos_x = models.DecimalField(max_digits=9, decimal_places=4, null=True, blank=True)
    pos_y = models.DecimalField(max_digits=9, decimal_places=4, null=True, blank=True)
    rotation = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    side = models.CharField(max_length=6, choices=SIDE_CHOICES, blank=True)

    class Meta:
        ordering = ['reference']
        constraints = [models.UniqueConstraint(fields=['design', 'reference'], name='unique_design_bom_reference')]

    def __str__(self):
        return f'{self.design}: {self.reference} = {self.part}'

    @property
    def reference_sort_key(self):
        """Natural sort key for `reference` so e.g. "R2" sorts before "R11".

        Plain string ordering (the DB-level `Meta.ordering` above) treats reference
        designators as opaque text, so "R11" sorts before "R2". Splitting into a
        (letter prefix, numeric value, remainder) tuple sorts numerically within
        each prefix instead.
        """
        prefix, number, suffix = _REFERENCE_SPLIT_RE.match(self.reference).groups()
        return (prefix.upper(), int(number) if number else -1, suffix.upper())


class PartSubstitution(models.Model):
    """A part that can be used as a possible substitution for another part."""
    part = models.ForeignKey(Part, on_delete=models.CASCADE, related_name='substitutions')
    substitute = models.ForeignKey(Part, on_delete=models.CASCADE, related_name='substitute_for')

    class Meta:
        unique_together = [('part', 'substitute')]
        ordering = ['substitute__name']

    def __str__(self):
        return f'{self.substitute} can substitute {self.part}'


class PartSource(models.Model):
    """A supplier's listing for a Part: one manufacturer SKU as stocked by one supplier.

    Stock is held here rather than on PartSourceVariant because suppliers such as
    DigiKey sell the same physical inventory pool under several packaging-specific SKUs
    (e.g. cut tape vs. tape & reel) that all report the same stock level but different
    pricing — those become separate PartSourceVariant rows under one PartSource.
    """
    part = models.ForeignKey(Part, on_delete=models.CASCADE, related_name='sources')
    supplier_name = models.CharField(max_length=200)
    manufacturer_sku = models.CharField(max_length=200, blank=True)
    stock = models.PositiveIntegerField(null=True, blank=True, help_text='Leave blank if stock level is unknown')

    class Meta:
        ordering = ['supplier_name']

    def __str__(self):
        return f'{self.part}: {self.supplier_name}'

    def save(self, *args, **kwargs):
        """Save, then append a PartSourceStockHistory snapshot whenever stock changes.

        Overridden here (rather than logged at each call site) so every code path that
        writes stock - manual add, supplier refresh, or a direct admin edit - is captured
        for the availability-trend history, without every caller needing to remember to
        log it themselves.
        """
        is_new = self._state.adding
        old_stock = None if is_new else PartSource.objects.filter(pk=self.pk).values_list('stock', flat=True).first()
        super().save(*args, **kwargs)
        if is_new or old_stock != self.stock:
            self.stock_history.create(stock=self.stock)

    @property
    def has_stale_variant_data(self):
        """True if any of this listing's variants has never been refreshed, or was last
        refreshed more than STALE_REFRESH_THRESHOLD ago."""
        cutoff = timezone.now() - STALE_REFRESH_THRESHOLD
        return any(
            variant.last_refreshed is None or variant.last_refreshed < cutoff
            for variant in self.variants.all()
        )


class PartSourceStockHistory(models.Model):
    """A timestamped snapshot of a PartSource's stock level, written by PartSource.save()
    whenever stock changes. Grows over time into a history usable for availability-trend
    tracking; PartSource.stock itself is left untouched so nothing that reads current
    stock needs to change or join against this table.
    """
    source = models.ForeignKey(PartSource, on_delete=models.CASCADE, related_name='stock_history')
    stock = models.PositiveIntegerField(null=True, blank=True)
    recorded_dt = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_dt']
        verbose_name_plural = 'part source stock history'

    def __str__(self):
        return f'{self.source}: {self.stock} @ {self.recorded_dt}'


class PartSourceVariant(models.Model):
    """A specific orderable SKU/packaging option under a PartSource listing."""
    source = models.ForeignKey(PartSource, on_delete=models.CASCADE, related_name='variants')
    supplier_sku = models.CharField(max_length=200, blank=True)
    packaging = models.CharField(max_length=100, blank=True)
    url = models.URLField(blank=True)
    moq = models.PositiveIntegerField(null=True, blank=True, help_text='Minimum order quantity; leave blank if unknown')
    last_refreshed = models.DateTimeField(
        null=True, blank=True, help_text='When pricing/stock was last fetched from the supplier API'
    )

    class Meta:
        ordering = ['supplier_sku']

    def __str__(self):
        return f'{self.source}: {self.supplier_sku}'


class PartPriceBreak(models.Model):
    """A quantity-based price break for a PartSourceVariant (e.g. qty 1 @ $0.50, qty 10 @ $0.45)."""

    # Most supplier APIs don't report a currency code at all, so it's stored as an
    # assumption (defaulting to USD) rather than something read from the API response.
    # This maps the stored ISO code to a display symbol; suppliers that report a real
    # currency should still store the ISO code here, not the symbol.
    CURRENCY_SYMBOLS = {
        'USD': '$',
        'AUD': '$',
        'EUR': '€',
        'GBP': '£',
        'JPY': '¥',
        'CNY': '¥',
    }

    variant = models.ForeignKey(PartSourceVariant, on_delete=models.CASCADE, related_name='price_breaks')
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=6)
    currency = models.CharField(max_length=10, default='USD')

    class Meta:
        ordering = ['quantity']
        unique_together = [('variant', 'quantity')]

    def __str__(self):
        return f'{self.variant}: qty {self.quantity} @ {self.currency} {self.price}'

    @property
    def symbol(self):
        return self.CURRENCY_SYMBOLS.get(self.currency, '')


class PartPriceBreakHistory(models.Model):
    """A timestamped snapshot of one of a PartSourceVariant's price breaks, written by
    _save_price_breaks() (see erp/views.py) whenever the resulting set of breaks differs
    from what was previously stored for that variant. Mirrors PartSourceStockHistory's
    role for stock: builds a growing history for future price-trend/fluctuation analysis
    without PartPriceBreak (the current-price table) needing to be queried any
    differently to show a simple current price. Kept as its own table, one row per
    (variant, quantity) pair per snapshot - same shape as PartPriceBreak itself - rather
    than merged into PartSourceStockHistory, since price breaks are per-variant (each
    packaging/SKU has its own) while stock is per-listing (PartSource); the two history
    tables are written from the same supplier refresh call so their recorded_dt values
    naturally land close together without needing to force them identical.
    """
    variant = models.ForeignKey(PartSourceVariant, on_delete=models.CASCADE, related_name='price_break_history')
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=6)
    currency = models.CharField(max_length=10, default='USD')
    recorded_dt = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_dt', 'quantity']
        verbose_name_plural = 'part price break history'

    def __str__(self):
        return f'{self.variant}: qty {self.quantity} @ {self.currency} {self.price} ({self.recorded_dt})'


class PartAsset(models.Model):
    """A file attachment on a Part (e.g. datasheet)."""
    part = models.ForeignKey(Part, on_delete=models.CASCADE, related_name='assets')
    file = models.FileField(upload_to=part_asset_upload_path)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    uploaded_dt = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.part}: {self.name}'

    @property
    def filename(self):
        return os.path.basename(self.file.name)

    def get_icon_class(self):
        ext = os.path.splitext(self.file.name)[1].lower()
        icons = {
            '.pdf': 'bi-file-earmark-pdf',
            '.zip': 'bi-file-earmark-zip',
            '.xlsx': 'bi-file-earmark-spreadsheet',
            '.csv': 'bi-file-earmark-spreadsheet',
        }
        return icons.get(ext, 'bi-paperclip')


class PartCategory(models.Model):
    """A category in a hierarchy for classifying parts (e.g. Passives > Resistors > SMD)."""
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.CASCADE, related_name='children'
    )
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name_plural = 'part categories'

    def __str__(self):
        return self.name


class BomLibrarySetting(models.Model):
    """Per-Fusion-library behaviour applied when importing parts from a BOM CSV."""
    library = models.CharField(max_length=200, unique=True, help_text='Fusion Electronics library name')
    ignore_device = models.BooleanField(
        default=False,
        help_text="When importing parts from this library, ignore the 'device' field: it is not used to "
                   "detect duplicates and is not stored on the part.",
    )
    ignore_package = models.BooleanField(
        default=False,
        help_text="When importing parts from this library, ignore the 'package' field: it is not used to "
                   "detect duplicates and is not stored on the part.",
    )
    ignore_value = models.BooleanField(
        default=False,
        help_text="When importing parts from this library, ignore the 'value' field: it is not used to "
                   "detect duplicates and is not stored on the part.",
    )

    class Meta:
        ordering = ['library']

    def __str__(self):
        return self.library


class BomExclusionRule(models.Model):
    """A rule that causes matching rows in a BOM CSV import to be skipped entirely.

    Each of library/device/package/value may be left blank to match any value for that field;
    a row is excluded only if it matches every non-blank field on the rule.
    """
    library = models.CharField(max_length=200, blank=True, help_text='Leave blank to match any library')
    device = models.CharField(max_length=200, blank=True, help_text='Leave blank to match any device')
    package = models.CharField(max_length=100, blank=True, help_text='Leave blank to match any package')
    value = models.CharField(max_length=100, blank=True, help_text='Leave blank to match any value')

    class Meta:
        ordering = ['library', 'device', 'package', 'value']

    def __str__(self):
        parts = [
            f'library={self.library or "(any)"}',
            f'device={self.device or "(any)"}',
            f'package={self.package or "(any)"}',
            f'value={self.value or "(any)"}',
        ]
        return ', '.join(parts)


class BomEquivalenceRule(models.Model):
    """A rule that remaps a (library, device, package, value) tuple to a different one during BOM import.

    from_library/from_device/from_package/from_value may be left blank to match any value for that field;
    a row matches only if it matches every non-blank "from" field on the rule.
    """
    from_library = models.CharField(max_length=200, blank=True, help_text='Leave blank to match any library')
    to_library = models.CharField(max_length=200, blank=True, help_text='Leave blank to leave the library unchanged')
    from_device = models.CharField(max_length=200, blank=True, help_text='Leave blank to match any device')
    to_device = models.CharField(max_length=200, blank=True, help_text='Leave blank to leave the device unchanged')
    from_package = models.CharField(max_length=100, blank=True, help_text='Leave blank to match any package')
    to_package = models.CharField(max_length=100, blank=True, help_text='Leave blank to leave the package unchanged')
    from_value = models.CharField(max_length=100, blank=True, help_text='Leave blank to match any value')
    to_value = models.CharField(max_length=100, blank=True, help_text='Leave blank to leave the value unchanged')

    class Meta:
        ordering = ['from_library', 'from_device', 'from_package', 'from_value']

    def __str__(self):
        from_parts = (
            f'{self.from_library or "(any)"} {self.from_device or "(any)"} '
            f'{self.from_package or "(any)"} {self.from_value or "(any)"}'
        )
        to_parts = (
            f'{self.to_library or self.from_library or "(any)"} '
            f'{self.to_device or self.from_device or "(any)"} '
            f'{self.to_package or self.from_package or "(any)"} '
            f'{self.to_value or self.from_value or "(any)"}'
        )
        return f'{from_parts} → {to_parts}'


class AssemblyCostSettings(models.Model):
    """Singleton record of global assembly-cost settings, used to calculate each Design's
    Build Costing breakdown (see device.models.Design)."""
    smt_joint_cost_cents = models.DecimalField(
        max_digits=8, decimal_places=4, default=0, verbose_name='Cost per SMT joint (cents)',
        help_text='e.g. 0.5 for half a cent',
    )
    pth_joint_cost_cents = models.DecimalField(
        max_digits=8, decimal_places=4, default=0, verbose_name='Cost per PTH joint (cents)',
        help_text='e.g. 5 for five cents',
    )
    labour_rate = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name='Assembly labour rate',
        help_text='Charge per hour of assembly labour',
    )
    kitting_margin_percent = models.DecimalField(
        max_digits=6, decimal_places=2, default=0, verbose_name='Parts kitting margin (%)',
        help_text='e.g. 20 for 20%',
    )
    conformal_coating_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    anti_shock_glue_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'Assembly cost settings'
        verbose_name_plural = 'Assembly cost settings'

    def __str__(self):
        return 'Assembly Cost Settings'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class BatchProductionStage(models.Model):
    """A production stage on a Batch, snapshotted from a ProductionStage at the time it was added."""
    NOT_STARTED = 'NOT_STARTED'
    IN_PROGRESS = 'IN_PROGRESS'
    ON_HOLD = 'ON_HOLD'
    DONE = 'DONE'

    STATUS_CHOICES = [
        (NOT_STARTED, 'Not Started'),
        (IN_PROGRESS, 'In Progress'),
        (ON_HOLD, 'On Hold'),
        (DONE, 'Done'),
    ]

    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name='production_stages')
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=7, default='#6c757d')
    order = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=NOT_STARTED)
    due_date = models.DateField(null=True, blank=True)
    completion_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.batch}: {self.order}. {self.name}'

    def get_bootstrap_table_class(self):
        classes = {
            self.NOT_STARTED: '',
            self.IN_PROGRESS: 'table-info',
            self.ON_HOLD: 'table-warning',
            self.DONE: 'table-success',
        }

        return classes.get(self.status, '')

    def get_status_color_class(self):
        classes = {
            self.NOT_STARTED: 'bg-secondary',
            self.IN_PROGRESS: 'bg-info',
            self.ON_HOLD: 'bg-warning',
            self.DONE: 'bg-success',
        }

        return classes.get(self.status, 'bg-secondary')

    def get_status_color(self):
        """Hex colour matching get_status_color_class(), for contexts without
        the Bootstrap/CoreUI stylesheet loaded (e.g. the printable page)."""
        colors = {
            self.NOT_STARTED: '#6c757d',
            self.IN_PROGRESS: '#39f',
            self.ON_HOLD: '#f9b115',
            self.DONE: '#2eb85c',
        }

        return colors.get(self.status, '#6c757d')
