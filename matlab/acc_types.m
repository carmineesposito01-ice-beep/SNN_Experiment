function T = acc_types(dt, nfrac)
%ACC_TYPES  Prototipi di tipo per `acc_iidm_open` type-parametrizzato (modello: snn_types.m).
%  dt = 'double' (riferimento algoritmico + plant cf_plant_lib) | 'fixed' (blocco HDL-ready).
%  nfrac (opz.) = bit frazionari del path fixed; i bit INTERI restano FISSI (il range non cambia),
%  varia solo la risoluzione -> e' la manopola dello sweep (run_acc_fixed_sweep), esattamente come
%  snn_types/run_fixed_sweep fanno per la rete.
%
%  I bit INTERI sono dimensionati con DUE criteri diversi, perche' i limiti hanno natura diversa --
%  applicare a tutti la stessa regola sarebbe misurare la cosa sbagliata:
%
%  (A) limitati dall'OSSERVAZIONE -> margine >= 2x sul massimo misurato (il dataset non e' il mondo).
%      Range misurati su 60 traiettorie x 1000 step coi parametri veri stimati dalla rete (spec SP3 §3):
%    st  : s, v, dv, v_l, s_safe, s_star         max misurato  465.77 -> int 10 (|x|<1024, 2.2x)
%    acc : v_free, a_z, a_iidm, a_cah, a_blend,
%          alf, a_l_bar, dd, z, dv^2/(2*s_safe)  min misurato -288.33 -> int 10 (|x|<1024, 3.6x)
%
%  (B) limitati da un CLAMP -> basta che il tipo copra il limite: non e' una stima, non puo' sforare.
%      Un margine di 1.4x su un limite CERTO vale piu' di 2x su un massimo osservato.
%    par : v0,T,s0,a,b   il decode li vincola a [param_lo, param_hi] = [8 .5 1 .3 .5]..[45 2.5 5 2.5 3]
%                        (sigmoide * range + lo: non puo' uscirne)   -> int  6 (|x|<64, 1.4x su 45)
%    out : accel         il codice la clampa a [-9, a], con a <= 2.5 -> int  4 (|x|<16, 1.8x su 9)
  if nargin < 2, nfrac = 13; end
  switch dt
    case 'double'
      z = double([]);
      T = struct('st', z, 'par', z, 'acc', z, 'out', z);
    case 'fixed'
      f = nfrac;
      T = struct( ...
        'st',  fi([], true, 11 + f, f), ...   % Q10.f
        'par', fi([], true,  7 + f, f), ...   % Q6.f
        'acc', fi([], true, 11 + f, f), ...   % Q10.f
        'out', fi([], true,  5 + f, f));      % Q4.f
    otherwise
      error('acc_types:dt', 'dt deve essere ''double'' o ''fixed''');
  end
end
