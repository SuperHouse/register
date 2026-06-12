from django.db import models
from django.utils import timezone

from crm.models import Org


class Design(models.Model):
    name = models.CharField(max_length=255)
    sku = models.CharField(verbose_name='SKU', max_length=50)
    description = models.TextField(null=True, blank=True)
    owner = models.ForeignKey(Org, on_delete=models.PROTECT)


class DesignVersion(models.Model):
    design = models.ForeignKey(Design, on_delete=models.PROTECT)
    hw_version = models.CharField(max_length=20)
    description = models.TextField(null=True, blank=True)
    price = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['design', 'hw_version'], name='unique_design_version')]

    def __str__(self):
        return f'{self.sku}: {self.name} {self.hw_version}'

    def save(self):
        super().save()


def design_asset_upload_path(instance, filename):
    return f'design_assets/{instance.views_design.id}/{filename}'


class DesignAsset(models.Model):
    FUSION = 'FUSION'
    PCB_DESIGN = 'PCB_DESIGN'
    SCHEMATIC = 'SCHEMATIC'
    BOM = 'BOM'
    PCB_TOP = 'PCB_TOP'
    PCB_BOTTOM = 'PCB_BOTTOM'
    PCB_3D = 'PCB_3D'
    FIRMWARE = 'FIRMWARE'
    ATTACHMENT = 'ATTACHMENT'

    CORE_ASSET_TYPES = frozenset({FUSION, PCB_DESIGN, SCHEMATIC, BOM, PCB_TOP, PCB_BOTTOM, PCB_3D, FIRMWARE})

    ASSET_TYPE_CHOICES = [
        ('Design Files', [
            (FUSION, 'Fusion Electronics Project'),
            (PCB_3D, 'PCB 3D View'),
            (PCB_TOP, 'PCB Top View'),
            (PCB_BOTTOM, 'PCB Bottom View'),
            (SCHEMATIC, 'Schematic Design File'),
            (PCB_DESIGN, 'PCB Design File'),
            (BOM, 'Bill of Materials'),
            (FIRMWARE, 'Firmware Binary'),
        ]),
        ('Additional', [
            (ATTACHMENT, 'Attachment'),
        ]),
    ]

    design = models.ForeignKey(DesignVersion, on_delete=models.CASCADE)
    file = models.FileField(upload_to=design_asset_upload_path)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    asset_type = models.CharField(max_length=20, choices=ASSET_TYPE_CHOICES, default=ATTACHMENT)
    uploaded_dt = models.DateTimeField(default=timezone.now)
    internal = models.BooleanField(default=False, help_text='Do not show this asset to clients')

    class Meta:
        ordering = ['asset_type', 'name']

    def __str__(self):
        return f'{self.design}: {self.name} ({self.get_asset_type_display()})'

    @property
    def is_core(self):
        return self.asset_type in self.CORE_ASSET_TYPES

    @property
    def filename(self):
        return os.path.basename(self.file.name)

    def get_icon_color(self):
        """Returns an inline color style value for this asset type, or empty string for default."""
        colors = {
            self.PCB_DESIGN: '#198754',
            self.SCHEMATIC: "#b50d13",
        }
        return colors.get(self.asset_type, '')

    def get_icon_class(self):
        """Returns a Bootstrap Icons class for this asset type."""
        classes = {
            self.PCB_DESIGN: 'bi-cpu',
            self.SCHEMATIC: 'bi-diagram-3',
            self.BOM: 'bi-file-earmark-spreadsheet',
            self.PCB_TOP: 'bi-file-earmark-image',
            self.PCB_BOTTOM: 'bi-file-earmark-image',
            self.PCB_3D: 'bi-box',
            self.FIRMWARE: 'bi-file-earmark-binary',
            self.ATTACHMENT: 'bi-paperclip',
        }
        return classes.get(self.asset_type, 'bi-file-earmark')
