# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from dataclasses import dataclass
from pathlib import Path

from device.models import DesignAsset


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

    def extract(self, project_path, out_dir):
        """Write whatever Design Files this tool can produce from project_path into out_dir.

        Returns an ExtractedAssets. Raises CadImportError on failure.
        """
        raise NotImplementedError
