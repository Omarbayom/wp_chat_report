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

# Alarms drawn in the alarm lane, coloured by type. A Log-CSV row is treated as
# an **alarm** iff its text is a key here (exact, case-sensitive match); anything
# else in the Log is treated as a settings/data-change **event**. This is the full
# device alarm set (SRS A6.6–A6.51). Names must match exactly what the device
# writes in the Log's ``Alarm`` column — if a real export spells one differently,
# add that spelling here or it will show up in the events lane instead.
#
# NOTE: the SRS lists "High airway pressure" (A6.7) and "High Airway Pressure"
# (A6.21) as separate IDs; both spellings are kept so either is caught.
ALARM_COLORS = {
    # airway / inspiratory pressure
    "Low airway pressure":               "#ff6f61",
    "High airway pressure":              "#e6194b",
    "High Airway Pressure":              "#e6194b",
    "High Inlet Air Pressure":           "#d35400",
    "High Inlet Oxygen Pressure":        "#e67e22",
    "Paw Cross Check Fault":             "#c0392b",
    # apnea
    "Patient Apnea":                     "#006400",
    # PEEP
    "Low PEEP":                          "#42d4f4",
    "High PEEP":                         "#4363d8",
    # respiratory rate
    "Low Respiratory Rate":              "#2e8b57",
    "High Respiratory Rate":             "#3cb44b",
    # FIO2 / oxygen
    "Low FIO2 Concentration":            "#b19cd9",
    "High FIO2 Concentration":           "#8e44ad",
    "O2 Sensor Fault":                   "#6a0dad",
    # minute / tidal volume
    "Low Mve":                           "#469990",
    "High MVe":                          "#1abc9c",
    "Low Mvi":                           "#16a085",
    "High Mvi":                          "#0e8f77",
    "Tidal Volume not Achieved":         "#bfa100",
    "Tidal Volume Exceeded":             "#daa520",
    # sensor faults
    "Air Inlet Pressure Sensor Fault":   "#7f8c8d",
    "O2 Inlet Pressure Sensor Fault":    "#95a5a6",
    "O2 Inlet Flow Sensor Fault":        "#a6acaf",
    "Inhalation Pressure Sensor Fault":  "#616a6b",
    "Air inlet flow sensor fault":       "#839192",
    "Exhalation Pressure Sensor Fault":  "#566573",
    "Exhalation Flow Sensor Fault":      "#808b96",
    # patient circuit / obstruction
    "Check Patient Circuit":             "#f58231",
    "Check Patient Circuit Reconnection Failure": "#cb4335",
    "Obstruction":                 "#000000",
    "HFO2T Obstruction Alarm":           "#d68910",
    # gas / air / O2 supply
    "Low Air Supply":                    "#808000",
    "Low O2 Supply":                     "#911eb4",
    "Low Gas Supply":                    "#9a6324",
    # flow
    "High Flow":                         "#e74c3c",
    "Low Flow":                          "#f39c12",
    # power / battery
    "AC Power Loss":                     "#f032e6",
    "Battery Low":                       "#e91e63",
    "Battery Critically Low":            "#ad1457",
    "Battery disconnected":              "#880e4f",
    # communication / system
    "Communication Loss":                "#34495e",
    "Internal communication loss":       "#2c3e50",
    "Screen Disconnection":              "#17202a",
    "Pressure Regulation Limited":       "#808080",
    "Standby":                           "#5d6d7e",
    "Button Stuck":                      "#7d3c98",
}
