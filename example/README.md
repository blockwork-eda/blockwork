# Example Project

## Running Testbench

```bash
$> bw exec -- make -f bench/Makefile run_cocotb
```

## Viewing Waves

```bash
$> bw tool gtkwave ../example.scratch/waves.lxt
```

## Running workflows
```bash
$> bw wf build -p ex -t top:design
$> bw wf test -p ex -t top:design
$> bw wf lint -p ex -t top:design
```