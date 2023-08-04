PARENT_DIRX := $(dir $(lastword $(MAKEFILE_LIST)))

all: run_cocotb

clean:: clean_cocotb

# ==============================================================================
# Icarus Verilog Setup
# ==============================================================================

export IVERILOG_DUMPER := lxt

# ==============================================================================
# cocotb
# ==============================================================================

SIM                 ?= icarus
TOPLEVEL_LANG       ?= verilog
VERILOG_SOURCES     += $(wildcard $(PARENT_DIRX)/../design/*.sv) /scratch/top.sv
SIM_BUILD           ?= /scratch/sim_build
COCOTB_RESULTS_FILE ?= /scratch/results.xml
SIM_WAVES           ?= /scratch/waves.lxt
TOPLEVEL            ?= top
MODULE              ?= bench
COMPILE_ARGS        += -D sim_icarus
PLUSARGS            += +WAVE_FILE=$(SIM_WAVES)

export PYTHONPATH := $(PYTHONPATH):$(PARENT_DIRX)

include $(shell cocotb-config --makefiles)/Makefile.sim

/scratch/top.sv: /project/design/top.sv.mako
	@python3 -c "from mako.template import Template; \
	             fh = open('$@', 'w'); \
	             fh.write(Template(filename='$<').render()); \
	             fh.flush(); \
	             fh.close() "

.PHONY: run_cocotb $(COCOTB_RESULTS_FILE)
run_cocotb: $(COCOTB_RESULTS_FILE)

.PHONY: clean_cocotb
clean_cocotb:
	rm -rf sim_build $(COCOTB_RESULTS_FILE)
