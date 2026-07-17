function [num, den] = iidm_nd(k, st) %#codegen
%IIDM_ND  [SP4-M-FSM] (num,den) della divisione k, presi dallo stato `st`. UNICA implementazione: la
%  chiamano sia il model (acc_iidm_fsm) sia la chart del blocco M (che li manda al blocco Divide).
%
%  Le 5 divisioni a divisore VARIABILE (ordine = dipendenze: q3 dopo q1 via s_star; q5 dopo q3/q4 via
%  a_iidm/a_cah). Espressioni VERBATIM da acc_iidm_open (righe 56, 58, 59, 68, 70).
%
%  ENTRAMBI in T.acc: il cast e' LOSSLESS (la fimath di acc_types ha Product/SumMode SpecifyPrecision
%  a 11+f bit con f=8 -> ogni prodotto/somma e' GIA' Q10.8 = T.acc; e T.par Q6.8 ⊂ T.acc Q10.8, stessi
%  frazionari). Serve perche' (a) una variabile non puo' cambiare tipo fra i rami (§9) e (b) il blocco
%  Divide ha porte di tipo fisso. G1 ha provato la bit-identita' proprio su coppie in T.acc; G2 ri-verifica
%  end-to-end che il cast non muova un bit.
  T = acc_types('fixed');           % costruito DENTRO (vedi iidm_prep): HDL Coder rifiuta lo struct come arg
  num = cast(0, 'like', T.acc);
  den = cast(1, 'like', T.acc);
  if k == 1                                   % q1 = vq*dq / (2*sab)            -> s_star
    num(:) = st.vq * st.dq;
    den(:) = 2*st.sab;
  elseif k == 2                               % q2 = vq / v0f                   -> v_free
    num(:) = st.vq;
    den(:) = st.v0f;
  elseif k == 3                               % q3 = s_star / s_safe            -> z
    num(:) = st.s_star;
    den(:) = st.s_safe;
  elseif k == 4                               % q4 = max(dq,0)^2 / (2*s_safe)   -> a_cah
    num(:) = max(st.dq, 0)^2;
    den(:) = 2*st.s_safe + 1e-6;
  else                                        % q5 = (a_iidm-a_cah) / bf        -> dd
    num(:) = st.a_iidm - st.a_cah;
    den(:) = st.bf + 1e-6;
  end
end
