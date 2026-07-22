function accel = iidm_final_c(st, ab) %#codegen
%IIDM_FINAL_C  [R11] Terza fase della finale: cast, selezione ACC e clamp -> accel.
%  Separata da iidm_final_b perche' il blend moltiplicativo e questa catena stavano nello stesso clock
%  (acc_3, 24 livelli, il collo a 52,3 MHz). Espressioni VERBATIM da iidm_final.
  T = acc_types('fixed');
  a_blend = cast(ab, 'like', T.acc);
  if st.a_iidm >= st.a_cah, ac = st.a_iidm; else, ac = a_blend; end
  accel = cast(min(max(ac, -9), st.af), 'like', T.out);
end
