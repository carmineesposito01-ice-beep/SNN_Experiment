function [af, bf] = iidm_ab(p) %#codegen
%IIDM_AB  [R2] I due parametri di accelerazione/decelerazione tipizzati. Estratti da iidm_prep perche'
%  ORA SERVONO A DUE CHIAMANTI: iidm_prep (che li mette nello struct) e iidm_sabx (che ne fa il
%  prodotto, ingresso della radice sequenziale).
%
%  ⚠️ Esistono per NON duplicare due righe di cast. Sembrano innocue -- `cast(max(p(4),1e-3),'like',T.par)`
%  copiata in due punti "e' ovviamente identica" -- ma e' esattamente la forma del buco §2.1 che costo'
%  l'82,4% dei control-step: due esemplari della stessa matematica che divergono in silenzio.
  T  = acc_types('fixed');
  af = cast(max(p(4), 1e-3), 'like', T.par);
  bf = cast(max(p(5), 1e-3), 'like', T.par);
end
