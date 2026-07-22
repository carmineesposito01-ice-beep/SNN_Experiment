function x = iidm_sabx_mul(af, bf) %#codegen
%IIDM_SABX_MUL  [R14] Il solo PRODOTTO af*bf, ingresso della radice.
%  Separato dai cast di iidm_ab perche' max/cast e moltiplicazione erano nello stesso clock -- era il
%  collo a 65,3 MHz (sX, 21 livelli). Fonte unica: la usano sia iidm_sabx (per il model) sia la chart.
  x = af * bf;
end
