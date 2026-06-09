"""Malody (.mc) -> osu!mania (.osu / .osz) conversion core.

Ported from the standalone malody2osu CLI (``convert.py``, original by Jakads,
modified by Eric Zhao). The conversion math — timing points, scroll-velocity
effects and hit objects — is preserved verbatim from the CLI. Only the
interactive shell around it (getch prompts, console title, update check,
crash-log writing) is dropped so the logic can run inside AstrBot.
"""

from __future__ import annotations

import json
import os
import zipfile
from dataclasses import dataclass, field
from typing import Optional

# File names disallowed on Windows/Linux; mirrors the CLI's sanitize_filename.
_INVALID_CHARS = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '\0']


def sanitize_filename(filename: str) -> str:
    """Strip characters illegal in file names, falling back to ``unknown``."""
    for char in _INVALID_CHARS:
        filename = filename.replace(char, '_')
    filename = filename.strip(' .')
    return filename if filename else "unknown"


class NotAValidMcError(Exception):
    """The file is not parseable as a Malody .mc chart."""


class NotKeyModeError(Exception):
    """The chart is valid but is not a Key (mode 0) difficulty."""


@dataclass
class ChartResult:
    """Outcome of converting one .mc file."""

    mc_path: str
    osu_path: str
    title: str
    artist: str
    background: Optional[str] = None  # absolute path to the background asset
    sound: Optional[str] = None       # absolute path to the audio asset


@dataclass
class OszResult:
    """Outcome of building one .osz mapset."""

    osz_path: str
    title: str = ""
    artist: str = ""
    converted: list[str] = field(default_factory=list)  # converted .mc basenames
    skipped: list[str] = field(default_factory=list)     # "name: reason" notes
    missing_assets: list[str] = field(default_factory=list)


# --- conversion helpers (verbatim from the CLI) -----------------------------

def _ms(beats, bpm, offset):
    return 1000 * (60 / bpm) * beats + offset


def _beat(b):  # beats = [measure, nth beat, divisor]
    return b[0] + b[1] / b[2]


def _col(column, keys):
    return int(512 * (2 * column + 1) / (2 * keys))


def convert_mc_file(mc_path: str) -> ChartResult:
    """Convert a single .mc file into a sibling .osu file.

    Raises :class:`NotAValidMcError` or :class:`NotKeyModeError` for charts that
    should be skipped (matching the CLI's FileWarning / KeyWarning behaviour).
    """
    try:
        with open(mc_path, encoding='utf-8') as mc:
            mc_file = json.loads(mc.read())
        mc_file['meta']['mode']
    except Exception as exc:  # noqa: BLE001 - any parse failure means "skip it"
        raise NotAValidMcError(os.path.basename(mc_path)) from exc

    if mc_file['meta']['mode'] != 0:
        raise NotKeyModeError(os.path.basename(mc_path))

    line = mc_file['time']
    meta = mc_file['meta']
    note = mc_file['note']
    sv = mc_file['effect'] if ('effect' in mc_file and len(mc_file['effect']) > 0) else None
    sv_map = sv is not None

    keys = meta["mode_ext"]["column"]

    soundnote = {}
    for x in note:
        if x.get('type', 0):
            soundnote = x

    bpm = [line[0]['bpm']]
    bpmoffset = [-soundnote.get('offset', 0)]

    if len(line) > 1:
        j = 0
        lastbeat = line[0]['beat']
        for x in line[1:]:
            bpm.append(x['bpm'])
            bpmoffset.append(_ms(_beat(x['beat']) - _beat(lastbeat), line[j]['bpm'], bpmoffset[j]))
            j += 1
            lastbeat = x['beat']

    title = meta["song"]["title"]
    artist = meta["song"]["artist"]
    preview = meta.get('preview', -1)
    titleorg = meta['song'].get('titleorg', title)
    artistorg = meta['song'].get('artistorg', artist)

    background = meta["background"]
    sound = soundnote.get("sound", "")
    creator = meta["creator"]
    version = meta["version"]

    bg_path = os.path.join(os.path.dirname(mc_path), background) if background else None
    sound_path = os.path.join(os.path.dirname(mc_path), sound) if sound else None

    osu_path = f'{os.path.splitext(mc_path)[0]}.osu'
    with open(osu_path, mode='w', encoding='utf-8') as osu:
        osuformat = ['osu file format v14',
                     '',
                     '[General]',
                     f'AudioFilename: {sound}',
                     'AudioLeadIn: 0',
                     f'PreviewTime: {preview}',
                     'Countdown: 0',
                     'SampleSet: Soft',
                     'StackLeniency: 0.7',
                     'Mode: 3',
                     'LetterboxInBreaks: 0',
                     'SpecialStyle: 0',
                     'WidescreenStoryboard: 0',
                     '',
                     '[Editor]',
                     'DistanceSpacing: 1.2',
                     'BeatDivisor: 4',
                     'GridSize: 8',
                     'TimelineZoom: 2.4',
                     '',
                     '[Metadata]',
                     f'Title:{title}',
                     f'TitleUnicode:{titleorg}',
                     f'Artist:{artist}',
                     f'ArtistUnicode:{artistorg}',
                     f'Creator:{creator}',
                     f'Version:{version}',
                     'Source:Malody',
                     'Tags:Malody Convert by Jakads',
                     'BeatmapID:0',
                     'BeatmapSetID:-1',
                     '',
                     '[Difficulty]',
                     'HPDrainRate:8',
                     f'CircleSize:{keys}',
                     'OverallDifficulty:8',
                     'ApproachRate:5',
                     'SliderMultiplier:1.4',
                     'SliderTickRate:1',
                     '',
                     '[Events]',
                     '//Background and Video events',
                     f'0,0,\"{background}\",0,0',
                     '',
                     '[TimingPoints]\n']
        osu.write('\n'.join(osuformat))

        bpmcount = len(bpm)
        for x in range(bpmcount):
            osu.write(f'{bpmoffset[x]},{60000 / bpm[x]},{int(line[x].get("sign", 4))},1,0,0,1,0\n')

        if sv_map:
            for n in sv:
                j = 0
                for b in line:
                    if _beat(b['beat']) > _beat(n['beat']):
                        j += 1
                    else:
                        continue

                j = bpmcount - j - 1

                if int(_ms(_beat(n["beat"]), bpm[j], bpmoffset[j])) >= bpmoffset[0]:
                    osu.write(
                        f'{_ms(_beat(n["beat"]) - _beat(line[j]["beat"]), bpm[j], bpmoffset[j])},'
                        f'-{100 / abs(n["scroll"]) if n["scroll"] != 0 else "1E+308"},'
                        f'{int(line[j].get("sign", 4))},1,0,0,0,0\n'
                    )

        osu.write('\n\n[HitObjects]')

        for n in note:
            if not n.get('type', 0) == 0:
                continue

            j = 0
            k = 0

            for b in line:
                if _beat(b['beat']) > _beat(n['beat']):
                    j += 1
                else:
                    continue

            if not n.get('endbeat') is None:
                for b in line:
                    if _beat(b['beat']) > _beat(n['endbeat']):
                        k += 1
                    else:
                        continue

            j = bpmcount - j - 1
            k = bpmcount - k - 1

            if int(_ms(_beat(n["beat"]), bpm[j], bpmoffset[j])) >= 0:
                osu.write(
                    f'\n{_col(n["column"], keys)},192,'
                    f'{int(_ms(_beat(n["beat"]) - _beat(line[j]["beat"]), bpm[j], bpmoffset[j]))}'
                )

                if n.get('endbeat') is None:  # Regular Note
                    osu.write(',1,0,0:0:0:')
                else:  # Long Note
                    osu.write(
                        f',128,0,{int(_ms(_beat(n["endbeat"]) - _beat(line[k]["beat"]), bpm[k], bpmoffset[k]))}:0:0:0:'
                    )

                if n.get('sound') is None:
                    osu.write('0:')
                else:  # Hitsound Note
                    osu.write('{0}:{1}'.format(n['vol'], n['sound'].replace('"', '')))

    return ChartResult(
        mc_path=mc_path,
        osu_path=osu_path,
        title=title,
        artist=artist,
        background=bg_path,
        sound=sound_path,
    )


def _build_osz(osz_path: str, charts: list[ChartResult]) -> tuple[list[str], list[str]]:
    """Pack converted .osu files plus their (deduplicated) assets into ``osz_path``.

    Returns (compressed_names, missing_asset_names).
    """
    compressed: list[str] = []
    missing: list[str] = []

    backgrounds = {c.background for c in charts if c.background}
    sounds = {c.sound for c in charts if c.sound}

    with zipfile.ZipFile(osz_path, 'w', zipfile.ZIP_DEFLATED) as osz:
        for chart in charts:
            arcname = f'{os.path.basename(chart.mc_path)}.osu'
            osz.write(chart.osu_path, arcname)
            compressed.append(arcname)
        for asset in backgrounds | sounds:
            if os.path.isfile(asset):
                osz.write(asset, os.path.basename(asset))
            else:
                missing.append(os.path.basename(asset))

    return compressed, missing


def _unique_osz_path(base_path_no_ext: str) -> str:
    """Return ``<base>.osz``, appending ``(n)`` if that file already exists."""
    candidate = base_path_no_ext
    suffix = 1
    while os.path.isfile(f'{candidate}.osz'):
        candidate = f'{base_path_no_ext} ({suffix})'
        suffix += 1
    return f'{candidate}.osz'


def _iter_mc_files(root: str):
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if os.path.splitext(name)[1].lower() == '.mc':
                yield os.path.join(dirpath, name)


def convert_to_osz(input_path: str, file_name: str, output_dir: str) -> OszResult:
    """Convert an uploaded ``.mc`` / ``.mcz`` / ``.zip`` into one ``.osz`` mapset.

    ``input_path`` is the local path of the uploaded file, ``file_name`` its
    original name (used to decide the type and to name the output), and
    ``output_dir`` a working directory the .osz (and, for archives, the
    extracted charts) are written into. Raises :class:`ValueError` when nothing
    convertible is found.
    """
    os.makedirs(output_dir, exist_ok=True)
    ext = os.path.splitext(file_name)[1].lower()

    if ext == '.mc':
        return _convert_single(input_path, file_name, output_dir)
    if ext in ('.mcz', '.zip'):
        return _convert_archive(input_path, file_name, output_dir)
    raise ValueError("仅支持 .mc / .mcz / .zip 文件。")


def _convert_single(input_path: str, file_name: str, output_dir: str) -> OszResult:
    # Work on a copy inside output_dir so the .osu lands next to it and the
    # caller can clean up everything by removing output_dir.
    work_mc = os.path.join(output_dir, sanitize_filename(os.path.basename(file_name)))
    if os.path.abspath(work_mc) != os.path.abspath(input_path):
        with open(input_path, 'rb') as src, open(work_mc, 'wb') as dst:
            dst.write(src.read())

    result = OszResult(osz_path="")
    try:
        chart = convert_mc_file(work_mc)
    except NotAValidMcError as e:
        raise ValueError(f"{e} 不是有效的 .mc 文件。") from e
    except NotKeyModeError as e:
        raise ValueError(f"{e} 不是 Key 模式谱面，无法转换为 osu!mania。") from e

    result.title = chart.title
    result.artist = chart.artist
    osz_path = _unique_osz_path(
        os.path.join(output_dir, sanitize_filename(f'{chart.artist} - {chart.title}'))
    )
    compressed, missing = _build_osz(osz_path, [chart])
    result.osz_path = osz_path
    result.converted = compressed
    result.missing_assets = missing
    return result


def _convert_archive(input_path: str, file_name: str, output_dir: str) -> OszResult:
    extract_dir = os.path.join(output_dir, 'extracted')
    os.makedirs(extract_dir, exist_ok=True)
    with zipfile.ZipFile(input_path) as archive:
        archive.extractall(extract_dir)

    charts: list[ChartResult] = []
    skipped: list[str] = []
    for mc_path in _iter_mc_files(extract_dir):
        try:
            charts.append(convert_mc_file(mc_path))
        except NotAValidMcError as e:
            skipped.append(f'{e}: 不是有效的 .mc 文件')
        except NotKeyModeError as e:
            skipped.append(f'{e}: 不是 Key 模式谱面')
        except Exception as e:  # noqa: BLE001 - keep going through the rest
            skipped.append(f'{os.path.basename(mc_path)}: 转换出错 ({e})')

    if not charts:
        raise ValueError("压缩包内没有可转换的 Key 模式 .mc 谱面。")

    stem = os.path.splitext(os.path.basename(file_name))[0]
    osz_path = _unique_osz_path(os.path.join(output_dir, sanitize_filename(stem)))
    compressed, missing = _build_osz(osz_path, charts)

    return OszResult(
        osz_path=osz_path,
        title=charts[0].title,
        artist=charts[0].artist,
        converted=compressed,
        skipped=skipped,
        missing_assets=missing,
    )
