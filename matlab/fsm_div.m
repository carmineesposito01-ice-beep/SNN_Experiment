function q = fsm_div(T, num, den) %#codegen
%FSM_DIV  [SP4-M-FSM] La divisione della forma FSM: num/den type-parametrica, UNICA implementazione.
%  Fixed -> divide(numerictype(T.acc),num,den): la STESSA di acc_div con recipN=0, cioe' SP3.
%  Double -> num/den (riferimento algoritmico).
%
%  Nella chart del blocco `Donatello_ACC_IIDM_M` le 5 divisioni a divisore VARIABILE non passano di qui:
%  sono sostituite dall'handshake verso HDLMathLib/Divide -- che G1 (probe_divide_bitexact) ha provato
%  BIT-IDENTICO a questa divide() su 300.000 coppie reali (ShiftAdd + RndMeth 'Zero' + OutType T.acc,
%  dmax=0). La divisione a divisore COSTANTE (DT del filtro OU) resta invece qui anche nella chart:
%  per una costante HDL Coder ripiega un moltiplicatore shallow, non e' un collo di profondita'.
%
%  NB: il reciproco-LUT (acc_types.recipN>0, variante L) NON e' contemplato: M usa la divisione ESATTA
%  (e' la ragione per cui L e' stata scartata -- document/SP4_ACC_IIDM_FAST.md).
  if ~isa(T.out, 'double')
    q = divide(numerictype(T.acc), num, den);
  else
    q = num / den;
  end
end
