"""FastAPI backend for the React cyclic-report web app.

Thin HTTP layer only — all the actual CSV parsing, alarm/event/mode
reconstruction, and patient-roster logic lives in the existing
``wa_report.cyclic_report`` package (see ``main.py``'s sys.path setup) and is
reused as-is, not reimplemented. This package exists purely so the same data
that currently gets baked into a static ``charts.html`` file can instead be
served as JSON to the React frontend in ``webapp/frontend``.
"""
