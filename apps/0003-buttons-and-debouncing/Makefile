PYTHON := ../../.venv/bin/python
PYTEST := ../../.venv/bin/pytest
RUFF := ../../.venv/bin/ruff

DEVICE := GW2AR-LV18QN88C8/I7
FAMILY := GW2A-18C
BOARD := tangnano20k

.PHONY: test lint verilog vcd bitstream flash clean

test:
	$(PYTEST) -v

lint:
	$(RUFF) check .

verilog:
	$(PYTHON) buttons.py --verilog

vcd:
	$(PYTHON) buttons.py --vcd

bitstream: verilog
	yosys -p "read_verilog build/buttons.v; synth_gowin -top button_counter -json build/buttons.json"
	nextpnr-himbaechel \
		--json build/buttons.json \
		--write build/buttons_pnr.json \
		--device $(DEVICE) \
		--vopt family=$(FAMILY) \
		--vopt cst=tangnano20k.cst
	gowin_pack -d $(FAMILY) -o build/buttons.fs build/buttons_pnr.json

flash: bitstream
	openFPGALoader -b $(BOARD) build/buttons.fs

clean:
	rm -rf build .pytest_cache __pycache__
