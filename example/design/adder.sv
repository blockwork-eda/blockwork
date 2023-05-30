module adder #(
      parameter WIDTH = 32
) (
      input  logic             i_clk
    , input  logic             i_rst
    , input  logic [WIDTH-1:0] i_value_a
    , input  logic [WIDTH-1:0] i_value_b
    , output logic [WIDTH-1:0] o_sum
    , output logic             o_overflow
);

logic [WIDTH-1:0] sum, sum_q;
logic             overflow, overflow_q;

always_comb begin : comb_add
    {overflow, sum} = i_value_a + i_value_b;
end

always_ff @(posedge i_clk, posedge i_rst) begin : ff_add
    if (i_rst) begin
        sum_q      <= 'd0;
        overflow_q <= 'd0;
    end else begin
        sum_q      <= sum;
        overflow_q <= overflow;
    end
end

assign o_sum      = sum_q;
assign o_overflow = overflow_q;

endmodule : adder
