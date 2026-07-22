function x = iidm_sabx(p) %#codegen
%IIDM_SABX  [R2] L'INGRESSO della radice: x = af*bf, da cui sab = sqrt(x).
%  Chiamata dal model (che poi fa sqrt_seq(x) in una volta) e dalla chart (che avvia su x la ricorrenza
%  sequenziale, uno stadio per clock). Una sola definizione di "cosa entra nella radice".
  [af, bf] = iidm_ab(p);
  x = iidm_sabx_mul(af, bf);   % [R14] il prodotto e' una funzione a se': la chart lo fa in un clock proprio
end
