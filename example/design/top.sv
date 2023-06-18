module top #(
      parameter WIDTH = 32
) (
      input  logic             i_clk
    , input  logic             i_rst
    , output logic [WIDTH-1:0] o_result
    , output logic             o_overflow
);

logic [WIDTH-1:0] count_a, count_b;

counter #(
      .WIDTH ( WIDTH )
) u_count_a (
      .i_clk   ( i_clk   )
    , .i_rst   ( i_rst   )
    , .o_count ( count_a )
);

counter #(
      .WIDTH ( WIDTH )
) u_count_b (
      .i_clk   ( i_clk   )
    , .i_rst   ( i_rst   )
    , .o_count ( count_b )
);

adder #(
      .WIDTH ( WIDTH )
) u_adder (
      .i_clk      ( i_clk      )
    , .i_rst      ( i_rst      )
    , .i_value_a  ( count_a    )
    , .i_value_b  ( count_b    )
    , .o_sum      ( o_result   )
    , .o_overflow ( o_overflow )
);

initial begin : init_waves
    string f_name;
    $timeformat(-9, 2, " ns", 20);
    if ($value$plusargs("WAVE_FILE=%s", f_name)) begin
        $display("%0t: Capturing wave file %s", $time, f_name);
        $dumpfile(f_name);
        $dumpvars(0, top);
    end else begin
        $display("%0t: No filename provided - disabling wave capture", $time);
    end
end

endmodule : top
