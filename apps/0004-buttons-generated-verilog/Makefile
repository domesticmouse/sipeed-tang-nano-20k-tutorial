PYTHON := ../../.venv/bin/python
PYTEST := ../../.venv/bin/pytest
RUFF := ../../.venv/bin/ruff

.PHONY: test lint verilog clean

test:
	$(PYTEST) -v

lint:
	$(RUFF) check .

verilog:
	$(PYTHON) buttons.py --verilog

clean:
	rm -rf build .pytest_cache __pycache__
