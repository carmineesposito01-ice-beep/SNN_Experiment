-- ann_mlp_flat: wrapper con porte FLAT (std_logic_vector) per istanziazione da Verilog.
-- xn: 4x19 = 76 bit; out: 5x21 = 105 bit. Solo remap di porte (nessuna logica, non datapath).
LIBRARY IEEE;
USE IEEE.std_logic_1164.ALL;
USE work.ann_mlp_pkg.ALL;

ENTITY ann_mlp_flat IS
  PORT( clk        : IN  std_logic;
        reset      : IN  std_logic;
        clk_enable : IN  std_logic;
        xn         : IN  std_logic_vector(75 DOWNTO 0);   -- {xn3,xn2,xn1,xn0}, ognuno 19b
        start      : IN  std_logic;
        ce_out     : OUT std_logic;
        out_flat   : OUT std_logic_vector(104 DOWNTO 0);  -- {o4,o3,o2,o1,o0}, ognuno 21b
        valid      : OUT std_logic );
END ann_mlp_flat;

ARCHITECTURE rtl OF ann_mlp_flat IS
  COMPONENT ann_mlp
    PORT( clk : IN std_logic; reset : IN std_logic; clk_enable : IN std_logic;
          xn : IN vector_of_std_logic_vector19(0 TO 3); start : IN std_logic;
          ce_out : OUT std_logic; out_rsvd : OUT vector_of_std_logic_vector21(0 TO 4);
          valid : OUT std_logic );
  END COMPONENT;
  SIGNAL xn_c  : vector_of_std_logic_vector19(0 TO 3);
  SIGNAL out_c : vector_of_std_logic_vector21(0 TO 4);
BEGIN
  xn_c(0) <= xn(18 DOWNTO 0);
  xn_c(1) <= xn(37 DOWNTO 19);
  xn_c(2) <= xn(56 DOWNTO 38);
  xn_c(3) <= xn(75 DOWNTO 57);
  out_flat(20 DOWNTO 0)   <= out_c(0);
  out_flat(41 DOWNTO 21)  <= out_c(1);
  out_flat(62 DOWNTO 42)  <= out_c(2);
  out_flat(83 DOWNTO 63)  <= out_c(3);
  out_flat(104 DOWNTO 84) <= out_c(4);
  u : ann_mlp PORT MAP( clk => clk, reset => reset, clk_enable => clk_enable, xn => xn_c,
                        start => start, ce_out => ce_out, out_rsvd => out_c, valid => valid );
END rtl;
