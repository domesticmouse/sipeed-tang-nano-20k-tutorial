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
	$(PYTHON) uart_tx.py --verilog

vcd:
	$(PYTHON) uart_tx.py --vcd

bitstream: verilog
	yosys -p "read_verilog build/uart_banner.v; synth_gowin -top uart_banner -json build/uart_banner.json"
	nextpnr-himbaechel \
		--json build/uart_banner.json \
		--write build/uart_banner_pnr.json \
		--device $(DEVICE) \
		--vopt family=$(FAMILY) \
		--vopt cst=tangnano20k.cst
	gowin_pack -d $(FAMILY) -o build/uart_banner.fs build/uart_banner_pnr.json

flash: bitstream
	openFPGALoader -b $(BOARD) build/uart_banner.fs

clean:
	rm -rf build .pytest_cache __pycache__
