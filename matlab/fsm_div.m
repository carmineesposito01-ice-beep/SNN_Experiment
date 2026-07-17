function q = fsm_div(num, den) %#codegen
%FSM_DIV  [SP4-M-FSM] La divisione della forma FSM: UNICA implementazione. FIXED-ONLY.
%  E' la STESSA divisione di acc_div con recipN=0, cioe' SP3: divide(numerictype(T.acc), num, den) con
%  la fimath di acc_types (RoundingMethod 'Zero', l'unica che HDL Coder genera per signed - SP3 §2).
%
%  ⚠️ `T` COSTRUITO DENTRO e non ricevuto come argomento: HDL Coder rifiuta uno struct di prototipi che
%     attraversa le funzioni -- "Struct in expression 'T' has an empty-typed field. This is not supported
%     for MATLAB-to-dataflow conversion" (i prototipi di acc_types sono fi([],...), campi VUOTI).
%     Chiamata qui dentro con argomento letterale, acc_types e' coder.const e viene ripiegata.
%     Conseguenza accettata: la forma FSM e' fixed-only. Il riferimento DOUBLE resta acc_iidm_open
%     (type-parametrico, invariato) -- lo prova run_plant_parity.
%
%  Nella chart del blocco M le 5 divisioni a divisore VARIABILE non passano di qui: sono sostituite
%  dall'handshake verso HDLMathLib/Divide, che G1 ha provato BIT-IDENTICO a questa divide() su 300.000
%  coppie reali (dmax=0). La divisione a divisore COSTANTE (DT del filtro OU) resta qui anche nel blocco:
%  per una costante HDL Coder ripiega un moltiplicatore shallow, non e' un collo di profondita'.
  T = acc_types('fixed');
  q = divide(numerictype(T.acc), num, den);
end
