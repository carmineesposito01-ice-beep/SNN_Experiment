function st = iidm_use_b(k, q, st) %#codegen
%IIDM_USE_B  [R5] Seconda meta': i prodotti e le selezioni, a partire dai quadrati gia' registrati.
%  Espressioni VERBATIM da iidm_use, con `min(q,10)^4` -> `st.uu^2` e `st.z^2` -> `st.zz`: identita'
%  garantita solo perche' uu/zz sono a LARGHEZZA PIENA (iidm_prep). Il cancello e' G2 sui 60000
%  control-step -- non si assume che le due forme coincidano, si prova.
  T = acc_types('fixed');
  if k == 1                                   % q1 -> s_star
    st.s_star(:) = st.s0f + max(st.vt + q, 0);   % [R15] vt = vq*Tf_ arriva da iidm_use_m

  elseif k == 2                               % q2 -> v_free
    st.v_free(:) = st.af*(1 - st.uu2);   % [R7] uu2 = uu^2 arriva da iidm_use_m

  elseif k == 3                               % q3 -> a_z / a_iidm (z e z^2 arrivano da iidm_use_a)
    below = (st.vq <= st.v0f);
    a_z = cast(st.af*st.w, 'like', T.acc);
    if st.z < 1
      if below, st.a_iidm(:) = st.v_free*st.w; else, st.a_iidm(:) = st.v_free; end
    else
      if below, st.a_iidm(:) = a_z;                   else, st.a_iidm(:) = st.v_free + a_z; end
    end

  elseif k == 4                               % q4 -> a_cah (+ clamp)
    st.a_cah(:) = st.a_l_bar - q;
    st.a_cah(:) = min(max(st.a_cah, -9), st.af);

  else                                        % q5 -> dd
    st.dd(:) = q;
  end
end
