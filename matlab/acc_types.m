function T = acc_types(dt, nfrac, recipN)
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
  % nfrac di DEFAULT = 8: il MINIMO che rispetta il budget DERIVATO. Misurato da run_acc_fixed_sweep
  % sul dataset INTERO (60 traj x 1000 step = 60.000 campioni, 2026-07-16, log sweep_nfrac8_60traj.log):
  %   budget  E_snn  (footprint in accel della quantizzazione GIA' accettata della rete):
  %                                   p99 = 0.272054   max = 1.48433  [m/s^2]
  %   nfrac=6 E_iidm  p99 = 0.324937  max = 1.78485  -> NON passa (l'IIDM diventerebbe la fonte
  %                                                     d'errore DOMINANTE, scavalcando la rete)
  %   nfrac=8 E_iidm  p99 = 0.156047  max = 0.83368  -> passa, margine ~1.75x su entrambi
  % ⚠️ Passa STRETTO: un dry-run su 2 traiettorie dava ~6x di margine, il dataset intero dice 1.75x.
  %    Le code stanno solo nel campione completo -> non tarare questo numero su pochi casi.
  if nargin < 2, nfrac = 8; end
  % recipN: strategia di divisione del path fixed. 0 = divide() digit-recurrence (SP3, combinatorio
  % profondo). >0 = reciproco a LUT a recipN punti + moltiplica (SP4 variante L). Vive nei tipi cosi'
  % la scelta e' coder.const e single-source. Default 0 = comportamento SP3 invariato.
  if nargin < 3, recipN = 0; end
  switch dt
    case 'double'
      z = double([]);
      T = struct('st', z, 'par', z, 'acc', z, 'out', z);
      T.recipN = 0;
    case 'fixed'
      f = nfrac;
      % La fimath fa parte del TIPO, non e' una decorazione locale. Due ragioni, entrambe misurate:
      %  1) RoundingMethod 'Zero' e' l'UNICA forma di divisione che HDL Coder genera per tipi signed
      %     ('Floor' vale solo per unsigned, 'Nearest' viene rifiutata) -- spec SP3 §2;
      %  2) attaccarla qui evita che una `setfimath` locale la cambi su una variabile gia' assegnata:
      %     il codegen rifiuta anche il cambio di FIMATH, non solo di tipo -- "Properties of fimath
      %     object must match. Property 'RoundMode' is 'nearest' ... but 'fix'". Mettendola nel
      %     prototipo, ogni cast(x,'like',T.*) la porta con se' e tutto combacia per costruzione.
      % Prodotti e somme a precisione FISSA: senza, i word-length crescerebbero a ogni operazione.
      FM = fimath('RoundingMethod', 'Zero', 'OverflowAction', 'Saturate', ...
                  'ProductMode', 'SpecifyPrecision', ...
                  'ProductWordLength', 11 + f, 'ProductFractionLength', f, ...
                  'SumMode', 'SpecifyPrecision', ...
                  'SumWordLength', 11 + f, 'SumFractionLength', f);
      % Prototipi con valore 0 e NON `fi([])`: un campo VUOTO e' "empty-typed" e HDL Coder lo rifiuta
      % quando lo struct dei tipi attraversa piu' funzioni -- "Struct in expression 'acc_types(''fixed'')'
      % has an empty-typed field. This is not supported for MATLAB-to-dataflow conversion" (SP4-M-FSM:
      % le funzioni-fase iidm_prep/nd/use/final). Come PROTOTIPO e' equivalente: `cast(x,'like',T.*)` usa
      % solo numerictype+fimath, che qui sono identici -> nessun cambiamento numerico (lo provano
      % run_plant_parity, run_block_acciidm_test e G2, tutti ri-eseguiti dopo questa modifica).
      T = struct( ...
        'st',  fi(0, true, 11 + f, f, FM), ...   % Q10.f
        'par', fi(0, true,  7 + f, f, FM), ...   % Q6.f
        'acc', fi(0, true, 11 + f, f, FM), ...   % Q10.f
        'out', fi(0, true,  5 + f, f, FM));      % Q4.f
      T.recipN = recipN;
    otherwise
      error('acc_types:dt', 'dt deve essere ''double'' o ''fixed''');
  end
end
