"""Script to fetch system voices from MiniMax API and output/update const.py.

Usage:
    python update_voices.py --api-key YOUR_API_KEY [--output const|file|update]

With --output const (default), prints the VOICE_IDS dict ready to paste into const.py.
With --output file, writes the VOICE_IDS dict to voices_output.py.
With --output update, directly updates VOICE_IDS in const.py (recommended).

Note: The MiniMax get_voice endpoint returns voices as a flat list without
language tags. The script groups them by language prefixes in the voice_id
when possible (e.g., "English_...", "Chinese_..."). Voices without a clear
language prefix are listed under "Uncategorized" for manual placement.
"""

import argparse
import asyncio
import os
from pathlib import Path
import re
import sys

import httpx

GET_VOICE_API = "https://api.minimax.io/v1/get_voice"

PROJECT_ROOT = Path(__file__).resolve().parent
CONST_PATH = PROJECT_ROOT / "custom_components" / "minimax" / "const.py"
SAFE_VOICE_ID = re.compile(r"^[A-Za-z0-9_.\- ]+$")

LANGUAGE_PREFIX_MAP = {
    "English_": "en-US",
    "Chinese (Mandarin)_": "zh-CN",
    "Cantonese_": "yue-CN",
    "Korean_": "ko-KR",
    "Japanese_": "ja-JP",
    "Spanish_": "es-ES",
    "Portuguese_": "pt-PT",
    "French_": "fr-FR",
    "Indonesian_": "id-ID",
    "German_": "de-DE",
    "Russian_": "ru-RU",
    "Italian_": "it-IT",
    "Dutch_": "nl-NL",
    "Vietnamese_": "vi-VN",
    "Arabic_": "ar-SA",
    "Turkish_": "tr-TR",
    "Ukrainian_": "uk-UA",
    "Thai_": "th-TH",
    "Polish_": "pl-PL",
    "Romanian_": "ro-RO",
    "Greek_": "el-GR",
    "greek_": "el-GR",
    "Czech_": "cs-CZ",
    "czech_": "cs-CZ",
    "Finnish_": "fi-FI",
    "finnish_": "fi-FI",
    "Hindi_": "hi-IN",
    "hindi_": "hi-IN",
    "Arrogant_": "ko-KR",
    "Robot_": "en-US",
}

MANUAL_PLACEMENTS = {
    "Chinese (Mandarin)_BashfulGirl": "zh-CN",
    "Chinese (Mandarin)_Crisp_Girl": "zh-CN",
    "Chinese (Mandarin)_Cute_Spirit": "zh-CN",
    "Chinese (Mandarin)_ExplorativeGirl": "zh-CN",
    "Chinese (Mandarin)_Gentle_Senior": "zh-CN",
    "Chinese (Mandarin)_Gentle_Youth": "zh-CN",
    "Chinese (Mandarin)_Gentleman": "zh-CN",
    "Chinese (Mandarin)_HK_Flight_Attendant": "zh-CN",
    "Chinese (Mandarin)_Humorous_Elder": "zh-CN",
    "Chinese (Mandarin)_IntellectualGirl": "zh-CN",
    "Chinese (Mandarin)_Kind-hearted_Antie": "zh-CN",
    "Chinese (Mandarin)_Kind-hearted_Elder": "zh-CN",
    "Chinese (Mandarin)_Laid_BackGirl": "zh-CN",
    "Chinese (Mandarin)_Lyrical_Voice": "zh-CN",
    "Chinese (Mandarin)_Male_Announcer": "zh-CN",
    "Chinese (Mandarin)_Mature_Woman": "zh-CN",
    "Chinese (Mandarin)_News_Anchor": "zh-CN",
    "Chinese (Mandarin)_Pure-hearted_Boy": "zh-CN",
    "Chinese (Mandarin)_Radio_Host": "zh-CN",
    "Chinese (Mandarin)_Reliable_Executive": "zh-CN",
    "Chinese (Mandarin)_Sincere_Adult": "zh-CN",
    "Chinese (Mandarin)_Soft_Girl": "zh-CN",
    "Chinese (Mandarin)_Southern_Young_Man": "zh-CN",
    "Chinese (Mandarin)_Straightforward_Boy": "zh-CN",
    "Chinese (Mandarin)_Stubborn_Friend": "zh-CN",
    "Chinese (Mandarin)_Sweet_Lady": "zh-CN",
    "Chinese (Mandarin)_Unrestrained_Young_Man": "zh-CN",
    "Chinese (Mandarin)_Warm-HeartedAunt": "zh-CN",
    "Chinese (Mandarin)_Warm_Bestie": "zh-CN",
    "Chinese (Mandarin)_Warm_Girl": "zh-CN",
    "Chinese (Mandarin)_Warm_HeartedGirl": "zh-CN",
    "Chinese (Mandarin)_Wise_Women": "zh-CN",
    "Robot_Armor": "en-US",
}


def _detect_language(voice_id: str) -> str:
    if voice_id in MANUAL_PLACEMENTS:
        return MANUAL_PLACEMENTS[voice_id]
    for prefix, lang in sorted(LANGUAGE_PREFIX_MAP.items(), key=lambda x: -len(x[0])):
        if voice_id.startswith(prefix):
            return lang
    return "Uncategorized"


def _format_voice_ids(voices: list[str], indent: int = 4) -> str:
    grouped: dict[str, list[str]] = {}
    for voice_id in voices:
        lang = _detect_language(voice_id)
        grouped.setdefault(lang, []).append(voice_id)

    lines: list[str] = []
    for lang in sorted(grouped.keys()):
        lines.append(f'{" " * indent}"{lang}": [')
        lines.extend(f'{" " * (indent + 4)}"{vid}",' for vid in sorted(grouped[lang]))
        lines.append(f"{' ' * indent}],")
    return "\n".join(lines)


async def fetch_voices(api_key: str) -> list[str]:
    """Fetch system voice IDs from the MiniMax API."""

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            GET_VOICE_API,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"voice_type": "system"},
        )
        response.raise_for_status()
        data = response.json()

    voices = data.get("system_voice", [])
    return [v["voice_id"] for v in voices]


def _sanitize_voices(voices: list[str]) -> list[str]:
    """Drop any voice ID that does not match the safe character set.

    Voice IDs come from the remote API and are embedded as Python string
    literals in const.py. Restricting to a known-safe charset ensures a
    malicious or malformed ID cannot break out of the literal or smuggle
    extra code into the generated source.
    """
    safe: list[str] = []
    for voice_id in voices:
        if not isinstance(voice_id, str) or not SAFE_VOICE_ID.match(voice_id):
            sys.stderr.write(f"Skipping unsafe voice_id: {voice_id!r}\n")
            continue
        safe.append(voice_id)
    return safe


def _resolve_const_path() -> Path:
    """Return the absolute path to const.py, refusing to leave PROJECT_ROOT."""
    resolved = CONST_PATH.resolve()
    if PROJECT_ROOT not in resolved.parents and resolved != PROJECT_ROOT:
        sys.stderr.write(f"Refusing to write outside project root: {resolved}\n")
        sys.exit(1)
    if not resolved.exists():
        sys.stderr.write(f"Could not find const.py at {resolved}\n")
        sys.exit(1)
    return resolved


def _update_const_py(voices: list[str]) -> None:
    safe_voices = _sanitize_voices(voices)
    const_path = _resolve_const_path()
    content = const_path.read_text(encoding="utf-8")
    formatted = _format_voice_ids(safe_voices)

    start_marker = "# --- VOICE_IDS START ---"
    end_marker = "# --- VOICE_IDS END ---"
    start_idx = content.find(start_marker)
    end_idx = content.find(end_marker)
    if start_idx == -1 or end_idx == -1:
        sys.stderr.write("Could not find VOICE_IDS markers in const.py\n")
        sys.exit(1)

    # Include the start marker, then the new block, then the end marker
    new_content = (
        content[:start_idx]
        + f"{start_marker}\nVOICE_IDS = {{\n{formatted}\n}}\n{end_marker}\n"
        + content[end_idx + len(end_marker) :]
    )
    const_path.write_text(new_content, encoding="utf-8")
    sys.stderr.write(f"Updated {const_path}\n")


async def main() -> None:
    """Run the voice update script."""
    parser = argparse.ArgumentParser(description="Fetch and format MiniMax voices")
    parser.add_argument(
        "--api-key", help="MiniMax API key (or set MINIMAX_API_KEY env var)"
    )
    parser.add_argument(
        "--output",
        choices=["const", "file", "update"],
        default="const",
        help="Output format: 'const' prints VOICE_IDS dict, "
        "'file' writes to voices_output.py, "
        "'update' directly updates const.py (recommended)",
    )
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("MINIMAX_API_KEY")
    if not api_key:
        sys.stderr.write(
            "Error: MINIMAX_API_KEY env var is required "
            "(--api-key argument is deprecated, use env var instead)\n"
        )
        sys.exit(1)

    if args.api_key:
        sys.stderr.write(
            "Warning: --api-key is deprecated and may expose credentials in process listings. "
            "Use MINIMAX_API_KEY env var instead.\n"
        )

    sys.stderr.write("Fetching voices from MiniMax API...\n")
    voice_ids = await fetch_voices(api_key)
    sys.stderr.write(f"Found {len(voice_ids)} system voices\n\n")

    if args.output == "update":
        _update_const_py(voice_ids)
        return

    formatted = _format_voice_ids(voice_ids)

    if args.output == "file":
        safe_voice_ids = _sanitize_voices(voice_ids)
        formatted = _format_voice_ids(safe_voice_ids)
        output_path = (PROJECT_ROOT / "voices_output.py").resolve()
        if PROJECT_ROOT not in output_path.parents:
            sys.stderr.write(f"Refusing to write outside project root: {output_path}\n")
            sys.exit(1)
        output_path.write_text(
            f"# Auto-generated voice list from MiniMax API\n\n"
            f"VOICE_IDS = {{\n{formatted}\n}}\n",
            encoding="utf-8",
        )
        sys.stderr.write(f"Written to {output_path}\n")
    else:
        sys.stdout.write(f"VOICE_IDS = {{\n{formatted}\n}}\n\n")

    grouped: dict[str, list[str]] = {}
    for vid in voice_ids:
        grouped.setdefault(_detect_language(vid), []).append(vid)
    uncategorized = grouped.pop("Uncategorized", [])
    sys.stderr.write(
        f"\nSummary: {len(voice_ids)} voices across {len(grouped)} languages\n"
    )
    for lang in sorted(grouped):
        sys.stderr.write(f"  {lang}: {len(grouped[lang])} voices\n")
    if uncategorized:
        sys.stderr.write(f"\n  Uncategorized ({len(uncategorized)} voices):\n")
        for v in sorted(uncategorized):
            sys.stderr.write(f"    {v}\n")


if __name__ == "__main__":
    asyncio.run(main())
