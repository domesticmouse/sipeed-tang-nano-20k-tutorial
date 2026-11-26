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
	$(PYTHON) pwm_fsm.py --verilog

vcd:
	$(PYTHON) pwm_fsm.py --vcd

bitstream: verilog
	yosys -p "read_verilog build/pwm_breather.v; synth_gowin -top pwm_breather -json build/pwm_breather.json"
	nextpnr-himbaechel \
		--json build/pwm_breather.json \
		--write build/pwm_breather_pnr.json \
		--device $(DEVICE) \
		--vopt family=$(FAMILY) \
		--vopt cst=tangnano20k.cst
	gowin_pack -d $(FAMILY) -o build/pwm_breather.fs build/pwm_breather_pnr.json

flash: bitstream
	openFPGALoader -b $(BOARD) build/pwm_breather.fs

clean:
	rm -rf build .pytest_cache __pycache__
