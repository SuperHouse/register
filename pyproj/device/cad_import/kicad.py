# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
import shutil
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

from django.conf import settings
from PIL import Image

from device.models import Design

from .base import CadExtractor, CadImportError, ExtractedAssets

# Fallback when KICAD_CLI is unset and kicad-cli isn't on PATH - a standard macOS install.
MACOS_KICAD_CLI = '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'

# Refuse archives that would unpack to more than this. Real projects are a few MB; this only
# guards against a zip bomb filling the disk.
MAX_UNPACKED_BYTES = 500 * 1024 * 1024

CLI_TIMEOUT_SECONDS = 180

# One row per reference designator, in the same reference/device/package/value/library
# columns as a Fusion BOM, so erp.views.design_bom_populate reads both the same way.
BOM_FIELDS = 'Reference,${SYMBOL_NAME},Footprint,Value,${SYMBOL_LIBRARY}'
BOM_LABELS = 'reference,device,package,value,library'

# kicad-cli renders onto a fixed-size canvas; the empty transparent margin around the board
# is trimmed afterwards (see _crop_to_content), leaving this many pixels.
RENDER_SIZE = 2000
RENDER_MARGIN = 20

# kicad-cli fits the board outline to the canvas, so parts that overhang the edge or stand
# tall would be clipped at zoom 1. Zooming out leaves room for them; the extra margin is
# trimmed afterwards anyway. --perspective was tried for the 3D view and clipped badly.
RENDER_VIEWS = {
    'pcb_top': ['--side', 'top', '--zoom', '0.9'],
    'pcb_bottom': ['--side', 'bottom', '--zoom', '0.9'],
    'pcb_3d': ['--side', 'top', '--rotate', '-45,0,45', '--zoom', '0.7'],
}


def _is_ignored(parts):
    """Whether an archive path should be skipped: macOS zip metadata, and KiCad's automatic
    backups folder, which often gets zipped up with the project and holds old copies."""
    return any(part == '__MACOSX' or part.endswith('-backups') or part.startswith('._') for part in parts)


def _is_project_entry(name):
    path = PurePosixPath(name)
    return path.suffix.lower() == '.kicad_pro' and not _is_ignored(path.parts)


def _safe_unpack(zip_path, dest):
    """Unpack zip_path into dest, refusing entries that would land outside it."""
    try:
        with zipfile.ZipFile(zip_path) as zf:
            members = [
                info for info in zf.infolist()
                if not info.is_dir() and not _is_ignored(PurePosixPath(info.filename).parts)
            ]
            if sum(info.file_size for info in members) > MAX_UNPACKED_BYTES:
                raise CadImportError(f'Archive unpacks to more than {MAX_UNPACKED_BYTES // (1024 * 1024)} MB.')
            for info in members:
                path = PurePosixPath(info.filename.replace('\\', '/'))
                if path.is_absolute() or '..' in path.parts:
                    raise CadImportError(f'Archive contains an unsafe path: {info.filename}')
                target = dest.joinpath(*path.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, open(target, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
    except zipfile.BadZipFile as e:
        raise CadImportError(f'Not a valid zip file: {e}') from e


def _find_project_file(root, upload_stem):
    """The project's .kicad_pro. If the archive holds more than one, prefer the one named
    like the upload, then the only one nearest the top of the archive."""
    candidates = [p for p in root.rglob('*') if p.is_file() and _is_project_entry(p.relative_to(root).as_posix())]
    if not candidates:
        if any(p.suffix.lower() == '.pro' for p in root.rglob('*.pro')):
            raise CadImportError(
                'Found only a KiCad 5 (.pro) project. Open it in KiCad 6 or later and save it, then upload it again.'
            )
        raise CadImportError('No .kicad_pro file found in the archive.')
    if len(candidates) == 1:
        return candidates[0]

    named = [p for p in candidates if p.stem == upload_stem]
    if len(named) == 1:
        return named[0]
    shallowest = min(len(p.relative_to(root).parts) for p in candidates)
    top = [p for p in candidates if len(p.relative_to(root).parts) == shallowest]
    if len(top) == 1:
        return top[0]
    names = ', '.join(sorted(p.relative_to(root).as_posix() for p in candidates))
    raise CadImportError(f'The archive holds more than one KiCAD project ({names}). Upload one project per zip.')


def _kicad_cli():
    if settings.KICAD_CLI:
        return list(settings.KICAD_CLI)
    if shutil.which('kicad-cli') is None and Path(MACOS_KICAD_CLI).exists():
        return [MACOS_KICAD_CLI]
    return ['kicad-cli']


def _run_cli(args, output, cwd):
    """Run one kicad-cli command that should write output, raising CadImportError if it
    can't be run, fails, or doesn't write output."""
    command = _kicad_cli() + [str(a) for a in args]
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=CLI_TIMEOUT_SECONDS)
    except FileNotFoundError as e:
        raise CadImportError(f'kicad-cli not found ({command[0]}). Set KICAD_CLI to its location.') from e
    except subprocess.TimeoutExpired as e:
        raise CadImportError(f'kicad-cli {args[0]} {args[1]} took longer than {CLI_TIMEOUT_SECONDS} seconds.') from e
    if result.returncode != 0 or not Path(output).exists():
        lines = (result.stderr or result.stdout).strip().splitlines()
        detail = lines[-1] if lines else f'exit status {result.returncode}'
        raise CadImportError(f'kicad-cli {args[0]} {args[1]} failed: {detail}')


def _crop_to_content(png_path):
    """Trim the transparent margin around a render, so the board fills the image like the
    Fusion renders do."""
    with Image.open(png_path) as image:
        if image.mode != 'RGBA':
            return
        bbox = image.getchannel('A').getbbox()
        if bbox is None:
            return
        left, top, right, bottom = bbox
        cropped = image.crop((
            max(left - RENDER_MARGIN, 0), max(top - RENDER_MARGIN, 0),
            min(right + RENDER_MARGIN, image.width), min(bottom + RENDER_MARGIN, image.height),
        ))
    cropped.save(png_path)


class KicadCadExtractor(CadExtractor):
    """A KiCAD 6+ project uploaded as a zip of its folder, via kicad-cli (KiCad 9 or later,
    for `pcb render`).

    The archive should hold the .kicad_pro with its matching .kicad_pcb and root .kicad_sch
    (hierarchical sub-sheets alongside), plus any project-local libraries the board uses.
    Produces the board and root schematic as-is, a BOM from the schematic, and top, bottom,
    and angled 3D renders of the board. Any kicad-cli failure fails the whole extraction, the
    same as a fusionextractor error does for Fusion.
    """
    cad_tool = Design.CAD_KICAD
    project_label = 'KiCAD Project'
    project_icon = 'img/filetypes/kicad.svg'
    file_extensions = ('.zip',)

    def accepts(self, uploaded_file):
        try:
            with zipfile.ZipFile(uploaded_file) as zf:
                return any(_is_project_entry(name) for name in zf.namelist())
        except zipfile.BadZipFile:
            return False
        finally:
            uploaded_file.seek(0)

    def extract(self, project_path, out_dir):
        project_path = Path(project_path)
        unpacked = out_dir / 'project'
        _safe_unpack(project_path, unpacked)

        project_file = _find_project_file(unpacked, project_path.stem)
        project_dir = project_file.parent
        board = project_file.with_suffix('.kicad_pcb')
        schematic = project_file.with_suffix('.kicad_sch')
        if not board.exists():
            raise CadImportError(f'No {board.name} next to {project_file.name} in the archive.')

        extracted = ExtractedAssets(pcb_design=board)
        if schematic.exists():
            extracted.schematic = schematic
            extracted.bom = out_dir / 'bom.csv'
            _run_cli([
                'sch', 'export', 'bom',
                '--fields', BOM_FIELDS, '--labels', BOM_LABELS,
                '--group-by', '', '--ref-range-delimiter', '',
                '--output', extracted.bom, schematic,
            ], extracted.bom, project_dir)

        for field, view_args in RENDER_VIEWS.items():
            png = out_dir / f'{field}.png'
            _run_cli([
                'pcb', 'render', *view_args,
                '--width', RENDER_SIZE, '--height', RENDER_SIZE,
                '--background', 'transparent', '--quality', 'basic',
                '--output', png, board,
            ], png, project_dir)
            _crop_to_content(png)
            setattr(extracted, field, png)

        return extracted
