"""Parse and merge WhatsApp chat exports.

A WhatsApp export is a ``.txt`` transcript plus media files in the same folder.
Message lines look like::

    10/11/2025, 5:06 pm - K. Galal: some text

Lines that do *not* start with a timestamp are continuations / captions of the
message above them (e.g. an image's caption, or a follow-up clinical note).
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

# Timestamp prefix, tolerant of the unicode narrow no-break space WhatsApp uses
# around am/pm and stray LTR/RTL marks.
_PREFIX_RE = re.compile(
    r"^(?P<date>\d{1,2}/\d{1,2}/\d{4}),"          # 10/11/2025,
    r"[\s ‎‏]+"
    r"(?P<time>\d{1,2}:\d{2}[\s ‎‏]*[ap]m)"  # 5:06 pm
    r"[\s ]*-[\s ]+"                     # ' - '
    r"(?P<rest>.*)$",
    re.IGNORECASE,
)

# After the prefix: "Sender: text".  Split on the first ": ".
_SENDER_RE = re.compile(r"^(?P<sender>[^:]+?):[\s ](?P<text>.*)$", re.DOTALL)

_ATTACH_RE = re.compile(r"^(?P<name>.+?)\s*\(file attached\)\s*$")

_SYSTEM_MARKERS = (
    "Messages and calls are end-to-end encrypted",
    "You deleted this message",
    "Waiting for this message",
    "changed the subject",
    "changed this group's icon",
    "created group",
    "added you",
)

SUPERVISOR_HINTS = ("galal",)  # senders treated as the supervisor, not the RT


@dataclass
class Message:
    dt: datetime
    sender: Optional[str]          # None for system lines
    text: str                      # header text (after "Sender: ")
    continuations: List[str] = field(default_factory=list)  # untimed lines
    attachment: Optional[str] = None   # filename if this message attached media
    source_dir: Path = field(default=Path("."))
    chat_name: str = ""
    is_system: bool = False
    is_deleted: bool = False
    is_media_omitted: bool = False

    @property
    def date_str(self) -> str:
        return self.dt.strftime("%d/%m/%Y")

    @property
    def time_str(self) -> str:
        return self.dt.strftime("%I:%M %p").lstrip("0")

    def text_lines(self) -> List[str]:
        """All human text on this message (header + continuations), excluding the
        attachment-filename header line and system/deleted noise."""
        lines: List[str] = []
        if not self.is_system and not self.is_deleted and self.attachment is None:
            if self.text and not self.is_media_omitted:
                lines.append(self.text)
        lines.extend(c for c in self.continuations if c.strip())
        return lines


def _parse_dt(date: str, time: str) -> Optional[datetime]:
    t = re.sub(r"[ ‎‏]", " ", time)
    t = re.sub(r"\s+", " ", t).strip().upper()
    for fmt in ("%d/%m/%Y %I:%M %p", "%m/%d/%Y %I:%M %p"):
        try:
            return datetime.strptime(f"{date} {t}", fmt)
        except ValueError:
            continue
    return None


def _classify_header(text: str) -> dict:
    """Return flags + attachment name for a message header text."""
    info = {"attachment": None, "is_deleted": False, "is_media_omitted": False}
    stripped = text.strip()
    if stripped in ("This message was deleted", "This message was deleted."):
        info["is_deleted"] = True
    elif stripped == "<Media omitted>":
        info["is_media_omitted"] = True
    else:
        m = _ATTACH_RE.match(stripped)
        if m:
            info["attachment"] = m.group("name").strip()
    return info


def parse_chat_file(path: Path) -> List[Message]:
    """Parse one .txt export into Message objects."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    source_dir = path.parent
    chat_name = path.stem
    messages: List[Message] = []
    current: Optional[Message] = None

    for line in raw.splitlines():
        m = _PREFIX_RE.match(line)
        if not m:
            # Continuation / caption of the previous message.
            if current is not None:
                current.continuations.append(line.rstrip())
            continue

        dt = _parse_dt(m.group("date"), m.group("time"))
        if dt is None:
            if current is not None:
                current.continuations.append(line.rstrip())
            continue

        rest = m.group("rest")
        sm = _SENDER_RE.match(rest)
        if sm:
            sender = sm.group("sender").strip()
            text = sm.group("text").strip()
            is_system = False
        else:
            # System notice (no "Sender:" part).
            sender = None
            text = rest.strip()
            is_system = any(mk in text for mk in _SYSTEM_MARKERS)

        info = _classify_header(text)
        current = Message(
            dt=dt,
            sender=sender,
            text=text,
            attachment=info["attachment"],
            source_dir=source_dir,
            chat_name=chat_name,
            is_system=is_system or any(mk in text for mk in _SYSTEM_MARKERS),
            is_deleted=info["is_deleted"],
            is_media_omitted=info["is_media_omitted"],
        )
        messages.append(current)

    return messages


def _looks_like_chat(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for _ in range(40):
                line = fh.readline()
                if not line:
                    break
                if _PREFIX_RE.match(line):
                    return True
    except OSError:
        return False
    return False


def _maybe_extract_zips(folder: Path) -> None:
    """Extract WhatsApp .zip exports that have not been extracted yet."""
    for zp in folder.rglob("*.zip"):
        target = zp.with_name(zp.stem + "_extracted")
        if target.exists():
            continue
        try:
            with zipfile.ZipFile(zp) as zf:
                names = zf.namelist()
                if any(n.lower().endswith(".txt") for n in names):
                    target.mkdir(parents=True, exist_ok=True)
                    zf.extractall(target)
        except (zipfile.BadZipFile, OSError):
            continue


def discover_chat_files(folder: Path) -> List[Path]:
    """Find all WhatsApp transcript .txt files under *folder* (recursively).

    Only auto-extracts .zip exports when no transcript exists yet (so we don't
    duplicate an export that was already unzipped). Identical transcripts (same
    name + size) are de-duplicated to avoid double-counting in the merge.
    """
    found = [p for p in folder.rglob("*.txt") if _looks_like_chat(p)]
    if not found:
        _maybe_extract_zips(folder)
        found = [p for p in folder.rglob("*.txt") if _looks_like_chat(p)]

    deduped: List[Path] = []
    seen: set[tuple[str, int]] = set()
    for p in sorted(found):
        try:
            key = (p.name, p.stat().st_size)
        except OSError:
            key = (p.name, -1)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(p)
    return deduped


def load_and_merge(folders) -> tuple[List[Message], List[Path]]:
    """Parse every chat under one or more *folders*, merge into a single timeline
    sorted by time. Identical transcripts (same name + size) found across folders
    are de-duplicated.

    *folders* may be a single path or an iterable of paths.

    Returns (messages, chat_files).
    """
    if isinstance(folders, (str, Path)):
        folders = [folders]

    chat_files: List[Path] = []
    seen: set[tuple[str, int]] = set()
    for f in folders:
        for p in discover_chat_files(Path(f)):
            try:
                key = (p.name, p.stat().st_size)
            except OSError:
                key = (p.name, -1)
            if key in seen:
                continue
            seen.add(key)
            chat_files.append(p)

    all_msgs: List[Message] = []
    for cf in chat_files:
        all_msgs.extend(parse_chat_file(cf))
    all_msgs.sort(key=lambda m: m.dt)
    return all_msgs, chat_files


def real_senders(messages: Iterable[Message]) -> List[str]:
    seen: List[str] = []
    for m in messages:
        if m.sender and m.sender not in seen:
            seen.append(m.sender)
    return seen


def rt_names(messages: Iterable[Message]) -> List[str]:
    """Senders that are not the supervisor (the respiratory therapists)."""
    out: List[str] = []
    for s in real_senders(messages):
        if not any(h in s.lower() for h in SUPERVISOR_HINTS):
            out.append(s)
    return out
