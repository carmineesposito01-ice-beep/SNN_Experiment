function st = iidm_use(k, q, st) %#codegen
%IIDM_USE  [SP4-M-FSM] Consuma il quoziente q della divisione k e aggiorna lo stato `st`. UNICA
%  implementazione: la chiamano sia il model (acc_iidm_fsm) sia la chart del blocco M (che passa il
%  `quot` arrivato dal blocco Divide quando validOut e' alto).
%
%  Espressioni VERBATIM da acc_iidm_open (righe 56, 58, 59-66, 68-69, 70). Aggiornamenti con
%  `st.campo(:) = ...`: mantengono il TIPO dichiarato in iidm_prep (§9 -- una variabile non puo'
%  cambiare tipo/fimath; e mai stringere un valore prima di usarlo: e' il meccanismo del bug §2.1).
  T = acc_types('fixed');                     % costruito DENTRO (vedi iidm_prep)
  if k == 1                                   % q1 -> s_star
    st.s_star(:) = st.s0f + max(st.vq*st.Tf_ + q, 0);

  elseif k == 2                               % q2 -> v_free
    st.v_free(:) = st.af*(1 - min(q, 10)^4);

  elseif k == 3                               % q3 -> z, poi a_z / a_iidm (dipendono da z e v_free)
    st.z(:) = min(q, 20);
    below = (st.vq <= st.v0f);
    a_z = cast(st.af*(1 - st.z^2), 'like', T.acc);
    if st.z < 1
      if below, st.a_iidm(:) = st.v_free*(1 - st.z^2); else, st.a_iidm(:) = st.v_free; end
    else
      if below, st.a_iidm(:) = a_z;                    else, st.a_iidm(:) = st.v_free + a_z; end
    end

  elseif k == 4                               % q4 -> a_cah (+ clamp)
    st.a_cah(:) = st.a_l_bar - q;
    st.a_cah(:) = min(max(st.a_cah, -9), st.af);

  else                                        % q5 -> dd
    st.dd(:) = q;
  end
end
