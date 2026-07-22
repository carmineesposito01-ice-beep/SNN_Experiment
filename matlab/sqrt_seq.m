function y = sqrt_seq(x) %#codegen
%SQRT_SEQ  [IIDM R2] Wrapper FUNZIONALE della radice sequenziale: setup -> nb passi -> fin.
%  Bit-identico a `sqrt(x)` di MATLAB per x = af*bf (numerictype(1,19,8)) -> y numerictype(1,10,4),
%  troncamento verso zero.
%
%  ⚠️ SINGLE SOURCE INTEGRALE (stessa struttura di div_seq): setup, passo e fin sono le TRE funzioni che
%  la chart chiama nei suoi stadi (SQRT-INIT / SQRT-STEP x10). Qui sono composte in una chiamata sola per
%  poterle PROVARE in modo esaustivo -- cio' che e' provato E' cio' che gira, negli stessi tipi.
%  Il model (acc_iidm_fsm) usa questo wrapper: non ha vincoli di clock, gli serve il valore subito.
%
%  ⚠️ La sqrt del riferimento e' GROSSOLANA (4 bit frazionari): va replicata COSI'. Una radice piu'
%     precisa divergerebbe -- l'obiettivo e' la bit-identita', non l'accuratezza.
  X = sqrt_seq_setup(x);                        % SQRT-INIT
  R = fi(0, 0, sqrt_seq_nb() + 2, 0);
  Q = fi(0, 0, sqrt_seq_nb(),     0);
  for k = 1:sqrt_seq_nb()                       % SQRT-STEP: in HW UN passo per ciclo (sk e' STATO)
    [X, R, Q] = sqrt_seq_step(X, R, Q);
  end
  y = sqrt_seq_fin(Q);                          % SQRT-FIN
end
