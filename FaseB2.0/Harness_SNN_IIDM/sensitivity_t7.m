function sensitivity_t7(workdir, idx, hold)
%SENSITIVITY_T7  Prova che OGNI cancello di T7a PUO' FALLIRE.
%  Un cancello mai visto fallire non e' un cancello: qui ciascuno viene messo in condizione di
%  scattare, e si verifica che scatti. Dove ha senso si verifica anche il contrario (che NON scatti
%  su una perturbazione che non deve rilevare).
%
%  ⚠️ Gira su UN SOLO scenario anche in modalita' 'full': la sensibilita' e' una proprieta' del
%     CANCELLO, non del dataset, e ripetere il replay del blocco su 99 scenari costerebbe ~46 min
%     senza aggiungere informazione.
%
%  PLANT-PAR non e' qui: la sua sensibilita' e' dimostrata separatamente perturbando il testbench
%  (ordine di update invertito -> 599 disallineamenti, primo al passo 2; ripristinato -> verde).
%  Richiede di ricompilare il TB, quindi non e' riproducibile in-process.
  if nargin < 3 || isempty(hold), hold = 700; end
  i1 = idx(1);
  fprintf('--- sensibilita'' dei cancelli T7a (scenario %d) ---\n', i1);

  V0 = t7_rtl_validate(workdir, i1, hold);
  assert(V0.nExact == 0 && V0.nRange == 0 && V0.nRep == 0, ...
         'sensitivity_t7: lo scenario di base non e'' pulito, la prova non significherebbe nulla');

  %% T7-EXACT — 1 LSB di Q4.8 su un accel della serie RTL
  f = fullfile(workdir, 'ser_1.txt'); bak = [f '.senbak'];
  copyfile(f, bak);
  cleaner = onCleanup(@() restore(bak, f));      % ripristina anche se qualcosa esplode
  L = readlines(f);
  r = split(strtrim(L(300)));
  r(6) = string(lower(dec2hex(typecast(t7_hexread(r(6)) + 1/256, 'uint64'), 16)));
  L(300) = strjoin(r, ' ');
  writelines(L, f);
  V1 = t7_rtl_validate(workdir, i1, hold);
  assert(V1.nExact == 1, 'T7-EXACT NON sensibile: 1 LSB alterato da'' %d disallineamenti', V1.nExact);
  fprintf('T7-EXACT     sensibile: 1 LSB alterato -> 1 disallineamento (al control-step %d)\n', V1.first.k);
  clear cleaner                                   % ripristina subito
  V2 = t7_rtl_validate(workdir, i1, hold);
  assert(V2.nExact == 0, 'ripristino fallito: il cancello e'' rimasto rosso');
  fprintf('             ripristino OK: torna a 0\n');

  %% PARAM-RANGE e NO-REPEAT — sulla matrice dei parametri letta
  R = t7_read_series(f);
  LO = [8 0.5 1 0.3 0.5]; HI = [45 2.5 5 2.5 3];
  P = R.params; P(5,1) = 1e9;
  assert(sum(any(P < LO | P > HI, 2)) == 1, 'PARAM-RANGE NON sensibile');
  fprintf('PARAM-RANGE  sensibile: parametro fuori dominio rilevato\n');
  fprintf('             margine reale: v0 in [%.3f, %.3f], limiti [%g, %g]\n', ...
          min(R.params(:,1)), max(R.params(:,1)), LO(1), HI(1));

  P = R.params; P(10,:) = P(9,:);
  assert(sum(all(P(2:end,:) == P(1:end-1,:), 2)) == 1, 'NO-REPEAT NON sensibile');
  P = R.params; P(10,1:4) = P(9,1:4);
  assert(sum(all(P(2:end,:) == P(1:end-1,:), 2)) == 0, ...
         'NO-REPEAT scatta su 4/5 parametri uguali: soglia sbagliata');
  fprintf('NO-REPEAT    sensibile: rileva 5/5 identici, NON scatta su 4/5\n');

  fprintf('--- tutte le sensibilita'' dimostrate ---\n');
end

function restore(bak, f)
  if isfile(bak), copyfile(bak, f); delete(bak); end
end
