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
	$(PYTHON) blinky.py --verilog

vcd:
	$(PYTHON) blinky.py --vcd

bitstream: verilog
	yosys -p "read_verilog build/blinky.v; synth_gowin -top blinky -json build/blinky.json"
	nextpnr-himbaechel \
		--json build/blinky.json \
		--write build/blinky_pnr.json \
		--device $(DEVICE) \
		--vopt family=$(FAMILY) \
		--vopt cst=tangnano20k.cst
	gowin_pack -d $(FAMILY) -o build/blinky.fs build/blinky_pnr.json

flash: bitstream
	openFPGALoader -b $(BOARD) build/blinky.fs

clean:
	rm -rf build .pytest_cache __pycache__
