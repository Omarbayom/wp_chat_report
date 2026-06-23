# wa_report — WhatsApp → Ventilation Monitoring Report

Turns one or more exported WhatsApp chats (a `.txt` transcript + its media) from
Ezz Medical's respiratory-therapist monitoring threads into a clean clinical
report in **Word (.docx)**, **PDF**, and **HTML**.

## What it produces

- **Header** — Hospital name.
- **Patient profile** — Patient name/ID, **Date-In** (first message, auto),
  **Date-Out** (last message, auto), duration, RT name(s), source-chat count, photo count.
- **Reporting cycles** — messages grouped into cycles by a time gap (default 15 min).
  Each cycle shows:
  - **Photos** — images only (videos/voice notes skipped), downscaled and embedded.
  - **Patient comfort / Humidifier state / Water-trap state** — lines from the RT
    matched by bilingual (EN+AR) keywords.
  - **General notes** — other substantive lines (settings changes, ABG/VBG, alarms, Q&A),
    labelled with who said it.
- **Untimed messages appendix** — every caption / continuation line (the "chats with
  no timestamp"), with a pointer to its parent message.

Multiple chats found under the folder are **merged into a single timeline sorted by
timestamp**.

## Install

```powershell
cd "C:\Users\omarbayom\Desktop\whatapp summry"
pip install -r wa_report\requirements.txt
```

`Pillow` downsizes/embeds photos. `python-docx` writes the Word file. `docx2pdf`
(Windows + Microsoft Word) converts the Word file to PDF; if Word isn't available the
DOCX and HTML are still produced and you can "Save as PDF" from either.

## Usage

```powershell
# Point at a single extracted chat folder
python -m wa_report "extract_0632" --hospital "Al-Salam Hospital" --patient "Bed 4 / Male 58"

# Point at a parent folder to MERGE several chats into one timeline
python -m wa_report "." --hospital "Al-Salam Hospital" --patient "Case A"

# Choose formats / cycle gap
python -m wa_report "extract_0530" --format html,docx --gap 20
```

If `--hospital` / `--patient` are omitted you'll be prompted. Outputs are written
next to the input folder as `report.docx`, `report.pdf`, `report.html`
(override the base name with `--out`).

## Options

| flag | default | meaning |
|------|---------|---------|
| `--out` | `report` | output base name |
| `--format` | `docx,pdf,html` | comma list of formats |
| `--gap` | `15` | minutes-gap that starts a new reporting cycle |
| `--hospital` / `--patient` | prompt | profile fields (not in the chat text) |
| `--max-dim` | `1000` | max embedded-image dimension (px) |

## Notes

- Keyword extraction is intentionally rough — it surfaces the relevant lines rather
  than inventing a summary, and unmatched lines still appear under *General notes* so
  nothing is lost. Keyword lists live in `extract.py` and are easy to extend.
- Arabic renders right-to-left automatically in HTML and Word.
