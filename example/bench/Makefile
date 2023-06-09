PARENT_DIRX := $(dir $(lastword $(MAKEFILE_LIST)))

all: run_cocotb

clean:: clean_cocotb

SIM_WAVES ?= run.lxt

# ==============================================================================
# Icarus Verilog Setup
# ==============================================================================

export IVERILOG_DUMPER := lxt

# ==============================================================================
# cocotb
# ==============================================================================

SIM             ?= icarus
TOPLEVEL_LANG   ?= verilog
VERILOG_SOURCES += $(wildcard $(PARENT_DIRX)/../design/*.sv)
TOPLEVEL        ?= top
MODULE          ?= bench
COMPILE_ARGS    += -D sim_icarus
PLUSARGS        += +WAVE_FILE=$(SIM_WAVES)

export PYTHONPATH := $(PYTHONPATH):$(PARENT_DIRX)

include $(shell cocotb-config --makefiles)/Makefile.sim

.PHONY: run_cocotb results.xml
run_cocotb: results.xml

.PHONY: clean_cocotb
clean_cocotb:
	rm -rf sim_build results.xml
