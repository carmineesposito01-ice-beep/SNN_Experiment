function st = iidm_use_a(k, q, st) %#codegen
%IIDM_USE_A  [R5/R16] Prima fase del consumo del quoziente: SOLO i clamp (nessuna moltiplicazione).
%  La legge IIDM ha due catene lunghe, ora distribuite su QUATTRO fasi:
%    k=2  min -> ^2 -> ^2 -> *af      (v_free)
%    k=3  min -> ^2 -> (1-z^2) -> *   (a_iidm)
%  Qui sta solo il primo anello: il clamp. Era il collo a 72,9 MHz (st_uu: min e quadrato insieme).
  if k == 2
    st.qm(:) = min(q, 10);
  elseif k == 3
    st.z(:)  = min(q, 20);
  end
end
