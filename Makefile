# Must point to the project's venv, not a bare system/launcher Python --
# a bare interpreter won't have pandas/openpyxl/pytest/etc. installed, and
# every target below will fail or silently no-op against it. Verified via
# literal `make <target>` calls, not just the equivalent python command,
# after this regressed to `py -3.14` at some point and broke 5 of 6 targets.
PY = .venv/Scripts/python.exe

.PHONY: load ratios test report dashboard api clean

load:
	$(PY) db/loader.py

# Points at the actual Ratio Engine entry point, not src/analytics/ratios.py --
# that file is a pure formula library (imported by cagr.py, cashflow_kpis.py,
# screener/engine.py, peer.py, and others) with no __main__ block by design.
# Giving it a side-effecting entry point would blur that separation; the real
# orchestrator that loads data, computes every ratio, and writes the
# financial_ratios table is populate_financial_ratios.py (Sprint 2).
ratios:
	$(PY) src/analytics/populate_financial_ratios.py

test:
	$(PY) -m pytest tests/ --html=reports/pytest_report.html --self-contained-html

report:
	$(PY) src/reports/portfolio_summary.py

dashboard:
	$(PY) -m streamlit run src/dashboard/app.py

api:
	$(PY) -m uvicorn src.api.main:app --port 8000

clean:
	$(PY) -c "import shutil, pathlib; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('__pycache__')]"
	$(PY) -c "import pathlib; [p.unlink() for p in pathlib.Path('.').rglob('*.pyc')]"
	$(PY) -c "import shutil, pathlib; p = pathlib.Path('.pytest_cache'); shutil.rmtree(p) if p.exists() else None"