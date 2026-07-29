PY = py -3.14

.PHONY: load ratios test report dashboard api clean

load:
	$(PY) src/etl/loader.py

ratios:
	$(PY) src/analytics/ratios.py

test:
	$(PY) -m pytest tests/ --html=reports/pytest_report.html --self-contained-html

report:
	$(PY) src/reports/portfolio_report.py

dashboard:
	$(PY) -m streamlit run src/dashboard/app.py

api:
	$(PY) -m uvicorn src.api.main:app --port 8000

clean:
	$(PY) -c "import shutil, pathlib; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('__pycache__')]"
	$(PY) -c "import pathlib; [p.unlink() for p in pathlib.Path('.').rglob('*.pyc')]"
	$(PY) -c "import shutil, pathlib; p = pathlib.Path('.pytest_cache'); shutil.rmtree(p) if p.exists() else None"