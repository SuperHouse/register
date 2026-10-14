# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
"""Extract Design Files from an uploaded CAD project (issue #140).

Each supported CAD tool has one CadExtractor subclass, registered in EXTRACTORS under its
Design.cad_tool value. design_asset_add picks one with extractor_for_filename() when a
CAD_PROJECT asset is uploaded and runs it through extract_and_save(), which is shared by
every tool. Adding a tool means one module here, one entry in EXTRACTORS, and one
Design.CAD_TOOL_CHOICES value. See CAD_IMPORT_PLAN.md.
"""
import tempfile
from pathlib import Path

from django.core.files import File

from device.models import DesignAsset

from .base import CadExtractor, CadImportError, ExtractedAssets
from .fusion import FusionCadExtractor

EXTRACTORS = {
    extractor.cad_tool: extractor
    for extractor in [FusionCadExtractor()]
}

DEFAULT_PROJECT_LABEL = 'CAD Project'


def get_extractor(cad_tool):
    """The extractor for a Design.cad_tool value, or None if blank/unsupported."""
    return EXTRACTORS.get(cad_tool)


def extractor_for_filename(filename):
    """The extractor whose project file extension matches filename, or None."""
    suffix = Path(filename).suffix.lower()
    for extractor in EXTRACTORS.values():
        if suffix in extractor.file_extensions:
            return extractor
    return None


def extract_and_save(extractor, design, project_path, stem):
    """Run extractor over project_path and save the results as design's core DesignAssets.

    Returns the list of asset types saved. Raises CadImportError on failure, before any
    existing asset has been replaced.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        extracted = extractor.extract(project_path, Path(tmpdir))
        return save_extracted_assets(design, extracted, stem)


def save_extracted_assets(design, extracted, stem):
    """Save each produced path as a core DesignAsset on design, replacing any existing asset
    of the same type. Files are named {stem}{name suffix}{extension of the extracted file}.

    Returns the list of asset types saved.
    """
    saved = []
    for asset_type, path, name_suffix in extracted.as_asset_list():
        existing = DesignAsset.objects.filter(design=design, asset_type=asset_type).first()
        if existing:
            existing.file.delete(save=False)
            existing.delete()

        asset = DesignAsset(design=design, name=stem, asset_type=asset_type)
        with open(path, 'rb') as f:
            asset.file.save(f'{stem}{name_suffix}{path.suffix}', File(f), save=True)
        saved.append(asset_type)
    return saved


__all__ = [
    'CadExtractor', 'CadImportError', 'DEFAULT_PROJECT_LABEL', 'EXTRACTORS', 'ExtractedAssets',
    'FusionCadExtractor', 'extract_and_save', 'extractor_for_filename', 'get_extractor',
    'save_extracted_assets',
]
