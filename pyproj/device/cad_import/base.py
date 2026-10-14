# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from device.models import DesignAsset


# Values of Placement.side - the same strings as erp.models.DesignBomEntry.TOP/BOTTOM, which
# this module can't import (erp.models imports device.models).
SIDE_TOP = 'TOP'
SIDE_BOTTOM = 'BOTTOM'


@dataclass
class Placement:
    """Where one part sits on the board, as stored on a DesignBomEntry: millimetres, rotation
    in degrees normalised to [0, 360), and SIDE_TOP or SIDE_BOTTOM."""
    pos_x: Decimal
    pos_y: Decimal
    rotation: Decimal
    side: str


def normalise_rotation(degrees):
    """KiCad reports e.g. -90 where EAGLE says 270; store both the EAGLE way, in [0, 360).
    Decimal's % keeps the dividend's sign (Decimal(-90) % 360 == -90), hence the correction."""
    remainder = Decimal(degrees) % 360
    return remainder + 360 if remainder < 0 else remainder


class CadImportError(Exception):
    """Extraction failed. The uploaded project file itself is kept; only extraction is skipped."""


@dataclass
class ExtractedAssets:
    """Paths an extractor managed to produce. Any of them can be None if the project didn't
    contain it, or the tool can't produce it."""
    bom: Path | None = None
    pcb_design: Path | None = None
    schematic: Path | None = None
    pcb_top: Path | None = None
    pcb_bottom: Path | None = None
    pcb_3d: Path | None = None

    def as_asset_list(self):
        """[(asset_type, path, name suffix)] for every path that was produced. The name suffix
        keeps the image filenames distinct, since every extracted asset is named after the
        uploaded project's stem."""
        return [
            (asset_type, path, name_suffix)
            for asset_type, path, name_suffix in [
                (DesignAsset.BOM, self.bom, ''),
                (DesignAsset.PCB_DESIGN, self.pcb_design, ''),
                (DesignAsset.SCHEMATIC, self.schematic, ''),
                (DesignAsset.PCB_TOP, self.pcb_top, '-top'),
                (DesignAsset.PCB_BOTTOM, self.pcb_bottom, '-bottom'),
                (DesignAsset.PCB_3D, self.pcb_3d, '-3d'),
            ]
            if path is not None
        ]


class CadExtractor:
    """Base class for one CAD tool's extractor."""
    cad_tool = None           # Design.cad_tool value this extractor handles
    project_label = None      # Design Files row label for this tool's CAD_PROJECT asset
    project_icon = None       # Optional static path of an icon image for that row
    file_extensions = ()      # Lower-case extensions (with dot) of this tool's project files
    placement_extensions = () # Extensions of this tool's PCB Design Files that read_placements reads

    def accepts(self, uploaded_file):
        """Whether an upload whose extension matches file_extensions really is this tool's
        project. Override when the extension alone is ambiguous (a .zip could hold anything).
        Must leave uploaded_file positioned at the start."""
        return True

    def extract(self, project_path, out_dir):
        """Write whatever Design Files this tool can produce from project_path into out_dir.

        Returns an ExtractedAssets. Raises CadImportError on failure.
        """
        raise NotImplementedError

    def read_placements(self, pcb_path):
        """Part positions from a PCB Design File (one of placement_extensions), as
        {reference designator: Placement}. Parts the file doesn't place are simply absent.
        Raises CadImportError if the file can't be read.
        """
        raise NotImplementedError
