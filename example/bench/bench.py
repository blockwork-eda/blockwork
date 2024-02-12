import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles


@cocotb.test()
async def smoke(dut):
    # Start a clock
    dut._log.info("Starting clock")
    cocotb.start_soon(Clock(dut.i_clk, 1, units="ns").start())
    # Drive reset high
    dut._log.info("Driving reset high")
    dut.i_rst.value = 1
    # Wait for 50 cycles
    dut._log.info("Waiting for 50 cycles")
    await ClockCycles(dut.i_clk, 50)
    # Drive the reset low
    dut._log.info("Driving reset high")
    dut.i_rst.value = 0
    # Run for 1000 cycles
    dut._log.info("Running for 1000 cycles")
    await ClockCycles(dut.i_clk, 1000)
