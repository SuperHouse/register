# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from fusionextractor.exceptions import FusionExtractorError
from fusionextractor.f3z import FusionProject

from device.models import Design

from .base import CadExtractor, CadImportError, ExtractedAssets


class FusionCadExtractor(CadExtractor):
    """Autodesk Fusion Electronics .f3z projects, via the fusionextractor library.

    The PCB 3D View thumbnail lives in a nested .f3d archive whose entries are partly
    zstd-compressed, so zipfile-zstd must be installed for it to be found.
    """
    cad_tool = Design.CAD_FUSION
    project_label = 'Fusion Electronics Project'
    project_icon = 'img/filetypes/fusion.svg'
    file_extensions = ('.f3z',)

    def extract(self, project_path, out_dir):
        try:
            with FusionProject(project_path) as proj:
                extracted = ExtractedAssets(
                    bom=proj.extract_bom(out_dir),
                    pcb_design=proj.extract_board(out_dir),
                    schematic=proj.extract_schematic(out_dir),
                    pcb_top=proj.extract_board_image('pcb_3d_top', out_dir),
                    pcb_bottom=proj.extract_board_image('pcb_3d_bottom', out_dir),
                )
                for preview in proj.get_previews(include_large_images=False):
                    if preview.source == '3d_model':
                        extracted.pcb_3d = out_dir / '3d_model__small.png'
                        extracted.pcb_3d.write_bytes(preview.data)
                        break
        except FusionExtractorError as e:
            raise CadImportError(str(e)) from e
        return extracted
