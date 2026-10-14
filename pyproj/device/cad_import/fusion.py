# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
import re
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation

from fusionextractor.exceptions import FusionExtractorError
from fusionextractor.f3z import FusionProject

from device.models import Design

from .base import SIDE_BOTTOM, SIDE_TOP, CadExtractor, CadImportError, ExtractedAssets, Placement, normalise_rotation

# An EAGLE element's rot attribute: "R90", or "MR90" for a part mirrored onto the bottom.
_BRD_ROT_RE = re.compile(r'^(M)?R(-?\d+(?:\.\d+)?)$')


class FusionCadExtractor(CadExtractor):
    """Autodesk Fusion Electronics .f3z projects, via the fusionextractor library.

    The PCB 3D View thumbnail lives in a nested .f3d archive whose entries are partly
    zstd-compressed, so zipfile-zstd must be installed for it to be found.
    """
    cad_tool = Design.CAD_FUSION
    project_label = 'Fusion Electronics Project'
    project_icon = 'img/filetypes/fusion.svg'
    file_extensions = ('.f3z',)
    placement_extensions = ('.brd',)

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

    def read_placements(self, pcb_path):
        """Positions from an EAGLE .brd (the PCB Design File a .f3z produces). Coordinates are
        EAGLE's own millimetres, so they match Fusion's CAM output.

        Reference designators (the <element name="..."> attribute) match the BOM CSV's
        `reference` column exactly, since both come from the same board - so they're the join
        key rather than library/device/package/value, which don't line up consistently between
        the two exports. A file that isn't valid XML yields no placements (moved unchanged
        from erp.views._parse_brd_placements, issue #143).
        """
        placements = {}
        try:
            elements = ET.parse(pcb_path).find('drawing/board/elements')
        except ET.ParseError:
            return placements
        if elements is None:
            return placements

        for element in elements.findall('element'):
            reference = element.get('name')
            if not reference:
                continue
            match = _BRD_ROT_RE.match(element.get('rot', 'R0'))
            try:
                placements[reference] = Placement(
                    pos_x=Decimal(element.get('x', '0')),
                    pos_y=Decimal(element.get('y', '0')),
                    rotation=normalise_rotation(match.group(2)) if match else Decimal('0'),
                    side=SIDE_BOTTOM if match and match.group(1) else SIDE_TOP,
                )
            except InvalidOperation:
                continue
        return placements
