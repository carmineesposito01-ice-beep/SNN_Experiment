function sv = decode_b(k, frac, N) %#codegen
%DECODE_B  [R4/R10/R17] Seconda fase del decode: tabella + interpolazione lineare -> s.
%  ⚠️ SINGLE SOURCE: composizione di decode_b1 (letture + differenza) e decode_b2 (interpolazione), che
%  la chart esegue in DUE clock. Composta qui per i chiamanti funzionali e per i cancelli.
  [s0v, delv] = decode_b1(k, N);
  sv          = decode_b2(s0v, delv, frac);
end
