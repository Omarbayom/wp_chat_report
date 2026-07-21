"""Constants for the cyclic <-> photo timeline report.

Mirrors the role of the original plotter's ``config.py``: the variables that may
go on the Y axis (with display units) and the plot colours.
"""

from __future__ import annotations

# Variables the user may put on the Y axis, with display units. Order here is the
# order they are offered / stacked.
VARIABLE_UNITS = {
    "VTi": "ml", "VTe": "ml", "PIP": "cmH2O", "Pmean": "cmH2O",
    "PEEP": "cmH2O", "RR": "/min", "FIO2": "%",
}
DEFAULT_VARIABLES = ["VTi", "VTe", "PIP"]

LINE_COLOR = "#0a6ebd"   # cyclic trace
MARK_COLOR = "#c0392b"   # photo-burst marker

# Alarms drawn in the alarm lane, coloured by type (from the original plotter).
# Only alarms listed here are shown; anything else in the Log CSV is ignored.
ALARM_COLORS = {
    "High Airway Pressure":        "#e6194b",
    "High Respiratory Rate":       "#3cb44b",
    "Check Patient Circuit":       "#f58231",
    "High PEEP":                   "#4363d8",
    "Low PEEP":                    "#42d4f4",
    "Obstruction":                 "#000000",
    "Low O2 Supply":               "#911eb4",
    "Low Gas Supply":              "#9a6324",
    "Low Air Supply":              "#808000",
    "AC Power Loss":               "#f032e6",
    "Tidal Volume not Achieved":   "#bfa100",
    "Low MVe":                     "#469990",
    "Pressure Regulation Limited": "#808080",
}
