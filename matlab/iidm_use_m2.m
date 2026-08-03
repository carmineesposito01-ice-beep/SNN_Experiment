function st = iidm_use_m2(k, st) %#codegen
%IIDM_USE_M2  [R16] Terza fase: il secondo quadrato di k=2 e la sottrazione di k=3.
%  Espressioni VERBATIM; i campi hanno il tipo PIENO del prodotto (vedi iidm_prep_b).
  if k == 2
    st.uu2(:) = st.uu^2;
  elseif k == 3
    st.w(:) = 1 - st.zz;
  end
end
