# Investigation: missing `Cyc. *` data on most Log entries

**Question raised:** in the detail popup for a mode/event entry, most rows show
"no cyclic data" under Cyclic readings even though the chart clearly has
cyclic samples at that time. Is this an app bug, or a device behavior — and
if it's a device behavior, is it a device defect?

**Data used:** `test/CyclicData 28-07-2026 114310.csv` and
`test/LogData 28-07-2026 114304.csv`, confirmed byte-identical (MD5) to the
copies on the Desktop.

## 1. App-level check

`load_log_entries()` in [alarms.py](../wa_report/cyclic_report/alarms.py)
captures every non-identity column from the Log CSV generically (no
hardcoded column list) into each row's `Settings` dict — so if the source
cell is blank, the app shows it as blank. Confirmed via `pandas` that the
`Cyc. *` columns in the DataFrame really are `NaN` for these rows.

## 2. Raw-file-level check (bypassing all app code)

Read `LogData 28-07-2026 114304.csv` directly with the stdlib `csv` module,
with no pandas/app parsing involved. The blank `Cyc. *` cells are genuinely
empty in the source file as exported by the device — not an artifact of the
app's CSV reading, dtype inference, or merge/dedup logic.

## 3. Scope of the pattern

Across 709 non-alarm Log rows spanning 48 distinct event/mode types, only
**"Standby Mode Activated"** ever carries a non-blank `Cyc. *` snapshot —
and even then only on 43 of its 117 occurrences. Every other event type is
0-for-0 (`load_log_entries()` docstring documents this).

## 4. What distinguishes the 43 "with data" rows from the 74 "without"

Looked at the **Log row immediately preceding** each "Standby Mode
Activated" row, grouped by whether the Standby row has a `Cyc.` snapshot:

| preceding row's `Alarm`/event text                          | has snapshot | count |
|---------------------------------------------------------------|:---:|:---:|
| **Check Patient Circuit**                                     | **39** | **39** |
| Home Page                                                      | 0 | 17 |
| Start Non-Invasive Ventilation                                 | 0 | 14 |
| Silence alarms                                                 | 0 | 8 |
| Startup Page                                                   | 0 | 5 |
| Low PEEP                                                       | 1 | 5 |
| Low O2 Supply                                                  | 0 | 4 |
| View Logs                                                      | 1 | 4 |
| Standby action                                                 | 0 | 3 |
| Organizational Settings Access                                 | 0 | 3 |
| Operation On Battery Started                                   | 0 | 3 |
| EzVent Started Successfully                                    | 0 | 3 |
| Add New Patient                                                | 0 | 2 |
| Alarm Limits Change                                            | 1 | 1 |
| Cancel EZVENT CHECK                                            | 0 | 1 |
| Force Shutdown Action.                                         | 0 | 1 |
| Operation On Battery Ended                                     | 0 | 1 |
| Maintenance Screen Access                                      | 0 | 1 |
| Confirm NIV CPAP-PS with Apnea Ventilation Mode...              | 1 | 1 |
| Start Invasive Ventilation                                     | 0 | 1 |

**Every one of the 39 Standby rows that follow a "Check Patient Circuit"
alarm has a `Cyc.` snapshot (39/39).** That single condition accounts for
39 of the 43 "with data" rows; the remaining 4 are singletons spread across
4 different preceding types, not a second clear pattern. No clustering by
date was found (the split is scattered across the whole 28/06–28/07 range),
which argues against a firmware-version or developing-fault explanation.

**Reading:** this looks like deliberate, conditional device logic — capture
a cyclic snapshot when Standby is entered specifically off the back of a
"Check Patient Circuit" alarm (a circuit-disconnect/obstruction condition),
and not on routine/manual transitions into Standby. That is exactly the
kind of diagnostic detail you'd want logged around a real alarm event, so
on its own this pattern reads as intended behavior rather than a defect.

## 5. SRS document check

Per the user's request, checked the two SRS documents on the Desktop for
anything documenting this behavior:

- **`SRS_Ventilation_Monitoring.docx`** — this is the SRS for *this
  reporting application* (ingestion, merge, charting, patient
  segmentation, outputs). It documents the Log CSV only as an external
  input format (`Alarm`, `Status`, `Date` columns) and does not specify
  the ventilator firmware's internal logic for what triggers a `Cyc. *`
  snapshot to be written into a Log row. Not the right document for this
  question.
- **`ERA 2 SRS V2.0.5.docx`** — this is the SRS for an unrelated
  requirements/document-management platform ("ERA 2"): permissions,
  baselines, standards/clauses, project scope, etc. No mention of
  "Standby", "Cyclic", "Cyc.", or "Circuit" anywhere in the document (0
  matches on all four terms). Not related to the EzVent device at all.

**Conclusion: neither document available to me specifies or confirms the
EzVent firmware's snapshot-on-Standby-after-Check-Patient-Circuit
behavior.** Only the ventilator's own firmware SRS / test protocol (if one
exists as a separate document, outside what's on this Desktop) could
confirm whether this is a specified, intended condition versus an
undocumented firmware quirk. Based on the data alone — the 39/39
consistency and the lack of date clustering — it looks like intended,
conditional logging rather than a random device defect, but that is an
inference from log behavior, not a confirmed spec citation.
