"""Resolve attachment filenames to real image files and downscale them.

Only images are kept (the user wants the photo sections to contain images only;
videos and voice notes are skipped).  Filenames can repeat across different
chats, so every name is resolved relative to its own source folder.
"""

from __future__ import annotations

import base64
import io
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from typing import Dict, Optional, Tuple

try:
    from PIL import Image, ImageOps
    _HAVE_PIL = True
except Exception:  # pragma: no cover - import guard
    _HAVE_PIL = False

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".heic"}


def is_image(name: str) -> bool:
    return Path(name).suffix.lower() in IMAGE_EXTS


# WhatsApp media names embed the date: IMG-20251118-WA0002.jpg -> 2025-11-18.
_NAME_DATE_RE = re.compile(r"-(\d{4})(\d{2})(\d{2})-", re.IGNORECASE)


def filename_date(name: str) -> Optional[date]:
    """Parse the YYYYMMDD date encoded in a WhatsApp media filename, if present."""
    m = _NAME_DATE_RE.search(Path(name).name)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def filename_date_str(name: str) -> str:
    d = filename_date(name)
    return d.strftime("%d/%m/%Y") if d else ""


def _fmt_dt(dt) -> str:
    # e.g. 18/11/2025 4:21 pm
    return dt.strftime("%d/%m/%Y ") + dt.strftime("%I:%M %p").lstrip("0").lower()


def photo_caption(name: str, dt=None) -> str:
    """Caption shown under a photo: the chat message timestamp (date + time),
    plus the filename's own date if it falls on a different day."""
    parts = []
    if dt is not None:
        parts.append(_fmt_dt(dt))
    fd = filename_date(name)
    if fd and (dt is None or fd != dt.date()):
        parts.append("img " + fd.strftime("%d/%m/%Y"))
    return "  ·  ".join(parts)


_DIR_INDEX: Dict[str, Dict[str, Path]] = {}


def _dir_index(source_dir: Path) -> Dict[str, Path]:
    """Lower-cased filename -> path for a folder, built once and cached.

    Avoids a full recursive walk for every missing/case-mismatched filename.
    """
    key = str(source_dir)
    idx = _DIR_INDEX.get(key)
    if idx is None:
        idx = {}
        try:
            for entry in os.scandir(source_dir):
                if entry.is_file():
                    idx[entry.name.lower()] = Path(entry.path)
        except OSError:
            pass
        _DIR_INDEX[key] = idx
    return idx


def resolve(name: str, source_dir: Path) -> Optional[Path]:
    p = source_dir / name
    if p.exists():
        return p
    # Case-insensitive lookup via the cached folder index (no recursive walk).
    return _dir_index(source_dir).get(Path(name).name.lower())


class MediaCache:
    """Downscales each image once; serves bytes / data-URIs / temp files."""

    def __init__(self, max_dim: int = 1000, quality: int = 80,
                 tmp_dir: Optional[Path] = None):
        self.max_dim = max_dim
        self.quality = quality
        self._bytes: Dict[Path, Optional[bytes]] = {}
        self._tmp: Dict[Path, Path] = {}
        self.tmp_dir = tmp_dir

    def _compute(self, path: Path) -> Optional[bytes]:
        """Downscale+encode one image. Pure (no cache writes) so it is safe to
        run in worker threads."""
        data: Optional[bytes] = None
        if _HAVE_PIL:
            try:
                with Image.open(path) as im:
                    im = ImageOps.exif_transpose(im)
                    if im.mode not in ("RGB", "L"):
                        im = im.convert("RGB")
                    im.thumbnail((self.max_dim, self.max_dim))
                    buf = io.BytesIO()
                    im.save(buf, format="JPEG", quality=self.quality, optimize=True)
                    data = buf.getvalue()
            except Exception:
                data = None
        if data is None:
            # No Pillow or unreadable -> use the raw file bytes.
            try:
                data = path.read_bytes()
            except OSError:
                data = None
        return data

    def scaled_bytes(self, path: Path) -> Optional[bytes]:
        if path in self._bytes:
            return self._bytes[path]
        data = self._compute(path)
        self._bytes[path] = data
        return data

    def prewarm(self, paths) -> None:
        """Downscale many images in parallel up front. Pillow releases the GIL
        during decode/encode, so threads give a near-linear speed-up. Results are
        cached, so the subsequent renderers reuse them for free."""
        todo = [p for p in dict.fromkeys(paths) if p not in self._bytes]
        if not todo:
            return
        workers = min(8, (os.cpu_count() or 4))
        with ThreadPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(self._compute, todo))
        for p, data in zip(todo, results):
            self._bytes[p] = data

    def data_uri(self, path: Path) -> Optional[str]:
        data = self.scaled_bytes(path)
        if data is None:
            return None
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"

    def temp_file(self, path: Path) -> Optional[Path]:
        """Write the scaled image to a temp .jpg and return its path (for DOCX)."""
        if path in self._tmp:
            return self._tmp[path]
        data = self.scaled_bytes(path)
        if data is None:
            return None
        if self.tmp_dir is None:
            import tempfile
            self.tmp_dir = Path(tempfile.mkdtemp(prefix="wa_report_"))
        out = self.tmp_dir / f"img_{len(self._tmp):04d}.jpg"
        try:
            out.write_bytes(data)
        except OSError:
            return None
        self._tmp[path] = out
        return out


def resolve_images(photo_names) -> Tuple[list, list]:
    """Given [(name, source_dir[, dt]), ...] return (resolved, missing_names),
    keeping only image files. Each resolved entry is a (Path, dt) tuple where dt
    is the chat message timestamp (or None)."""
    resolved = []
    missing = []
    for item in photo_names:
        name, source_dir = item[0], item[1]
        dt = item[2] if len(item) > 2 else None
        if not is_image(name):
            continue
        p = resolve(name, source_dir)
        if p is None:
            missing.append(name)
        else:
            resolved.append((p, dt))
    return resolved, missing
