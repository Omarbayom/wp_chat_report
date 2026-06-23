"""Offline keyword classification of chat lines.

Buckets the user cares about: patient comfort, humidifier state, water-trap
state.  Everything substantive that does not match one of those falls through
to general notes.  Bilingual (English + Arabic) keyword lists, case-insensitive.

This is intentionally rough: it surfaces the *lines* that mention a topic rather
than inventing a clinical summary.  Nothing substantive is dropped.
"""

from __future__ import annotations

import re
from typing import Dict, List, Set

COMFORT = "comfort"
HUMIDIFIER = "humidifier"
WATER_TRAP = "water_trap"
GENERAL = "general"

BUCKET_TITLES = {
    COMFORT: "Patient comfort",
    HUMIDIFIER: "Humidifier state",
    WATER_TRAP: "Water-trap state",
    GENERAL: "General notes",
}

# Keyword lists (lower-cased substrings). Arabic kept as-is.
_KEYWORDS: Dict[str, List[str]] = {
    COMFORT: [
        "comfort", "comfortable", "agitat", "calm", "restless", "settled",
        "tolerat", "fight the device", "fighting", "fights the device",
        "not fighting", "synchron", "asynchron", "dyssynchron",
        "double trigger", "double-trigger", "double triggering",
        "sedat", "anxious", "distress",
        "مريح", "مرتاح", "هادي", "هادئ", "متوافق", "متزامن", "متهيج",
        "عصبي", "مقاوم", "بيقاوم", "بيهيج",
    ],
    HUMIDIFIER: [
        "humidif", "humidity", "hme", "heated wire", "heated humidifier",
        "مرطب", "المرطب", "رطوبة", "الرطوبة", "ترطيب",
    ],
    WATER_TRAP: [
        "water trap", "water-trap", "watertrap", "water accumulation",
        "water accumulat", "accumulation of water", "condensation",
        "condensate", "condens", "emptied the water", "empty the water",
        "emptied water", "drain the water", "drained the water",
        "water in the tube", "water in tube", "water in the circuit",
        "fluid in the tube", "emptied it",
        "مياه", "المياه", "الميه", "ميه", "ماء", "الماء", "تفريغ", "تجميع المياه",
    ],
}

# Trivial acknowledgements to skip from general notes (lower-cased, stripped).
_ACKS = {
    "ok", "okay", "k", "thanks", "thank you", "yes", "no", "yep", "sure",
    "noted", "done", "normal", "fine", "good",
    "حاضر", "تمام", "ماشي", "نعم", "لا", "ايوه", "اوك", "اوكي", "ok 👍",
}


def match_buckets(line: str) -> Set[str]:
    """Return the set of state buckets a line mentions (may be empty)."""
    low = line.lower()
    hits: Set[str] = set()
    for bucket, kws in _KEYWORDS.items():
        if any(kw in low for kw in kws):
            hits.add(bucket)
    return hits


def is_substantive(line: str) -> bool:
    s = line.strip()
    if len(s) <= 2:
        return False
    if not any(ch.isalpha() for ch in s):   # emoji / numbers / punctuation only
        return False
    if s.lower() in _ACKS:
        return False
    return True


# Lines that are pure clock stamps the RT typed (e.g. "4:45", "6:15").
_CLOCK_RE = re.compile(r"^\d{1,2}:\d{2}\s*$")


def is_clock_note(line: str) -> bool:
    return bool(_CLOCK_RE.match(line.strip()))
