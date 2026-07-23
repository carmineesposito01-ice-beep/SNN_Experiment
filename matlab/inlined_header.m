function L = inlined_header()
%INLINED_HEADER  Intestazione della sezione dei sorgenti inlinati (condivisa dai due generatori).
  L = {
    '% ===================================================================================='
    '% Funzioni locali INLINATE dai sorgenti veri (build_hdl_variants le legge a build-time).'
    '% Le funzioni locali hanno precedenza sul path => il blocco e'' SELF-CONTAINED.'
    '% NON modificarle qui: si rigenerano con build_hdl_variants.'
    '% ===================================================================================='
  };
  L = L(:);
end


