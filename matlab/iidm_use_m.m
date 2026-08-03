function st = iidm_use_m(k, st) %#codegen
%IIDM_USE_M  [R7] Fase di MEZZO del consumo del quoziente: il secondo quadrato di k=2.
%  st.v_free = af*(1 - min(q,10)^4) aveva ANCORA due moltiplicatori in serie dopo R5 (uu^2, poi *af):
%  era il collo a 42,6 MHz (st_v_free, 25 livelli). Qui si isola uu^2 dietro un registro.
%  Il campo `uu2` ha il tipo PIENO (~104 bit): costa registri, non moltiplicatori -- il prodotto
%  esisteva gia', si sta solo mettendo un registro DOPO di esso.
  if k == 1
    st.vt(:) = st.vq * st.Tf_;   % [R15] il prodotto esce dal clock di s_star
  elseif k == 2
    st.uu(:) = st.qm^2;          % [R16] primo quadrato (qm = min(q,10) da iidm_use_a)
  elseif k == 3
    st.zz(:) = st.z^2;           % [R16] quadrato di z
  end
end
