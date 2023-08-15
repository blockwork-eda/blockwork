module counter #(
      parameter WIDTH = 32
) (
      input  logic             i_clk
    , input  logic             i_rst
    , output logic [WIDTH-1:0] o_count
);

logic [WIDTH-1:0] count, count_q;

always_comb begin : comb_count
    count = count_q + 'd1;
end

always_ff @(posedge i_clk, posedge i_rst) begin : ff_count
    if (i_rst) begin
        count_q <= 'd0;
    end else begin
        count_q <= count;
    end
end

assign o_count = count_q;

endmodule : counter
