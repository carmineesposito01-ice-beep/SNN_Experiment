function gen_donatello_point(outdir, decVariant, snnSrc, archStyle)
%  archStyle = 'chart' (default) | 'split' — una MF che fa tutto, oppure SNN e decode come DUE entita'
%    di sintesi distinte. Lo split rompe il muro d'integrazione (RESULTS.md §6): p3+R5 41,1 -> 56,4 MHz.
%  snnSrc = path del sorgente SNN (default 'snn_b2_fsm.m' = stato corrente, cioe' R9).
%    Per gli stati storici: 'snn_variants/snn_b2_fsm_R2.m' | '_R5.m' | '_R9.m' — snapshot CONGELATI,
%    che si compongono senza mutare il file condiviso.
%  decVariant = 'fused' | 'p3' | 'p5'  — profondita' di pipeline del DECODE ([A2]).
%  ⚠️ OBBLIGATORIO passarla: la versione precedente chiamava `build_hdl_variants()` SENZA argomento,
%  quindi ricostruiva col default 'fused' ANNULLANDO in silenzio la variante scelta dal chiamante.
%  Risultato: `a_balanced` (p3) e `a_ctrl_dec` (p5) sono usciti col decode FUSO e numeri identici a
%  `a_slow`. Un default silenzioso al posto di un errore = dati sbagliati che sembrano buoni.
%GEN_DONATELLO_POINT  Genera il VHDL del blocco Donatello COMPLETO (SNN + decode, LUT-64) allo stato
%  del worktree in cui viene eseguita. E' il generatore dei punti del Blocco A della campagna di
%  trade-off: ogni punto e' uno stato storico dei round SNN, ricostruito via `git worktree`.
%
%  USO (manuale o dal driver):
%    copiare questo file in <worktree>/matlab/ ed eseguire da li':
%      matlab -batch "gen_donatello_point('D:\zbd_snnwt\<tag>\out')"
%
%  ⚠️ PERCHE' IL BLOCCO COMPLETO E NON IL PROBE: i probe `snn_fwd_r*` su disco sono la SNN **senza
%  decode** (ingressi x1..x4, uscite o1..o5 = i raw). Erano lo STRUMENTO DI MISURA dei round, non
%  configurazioni: non si deployano. Uno studio che sceglie cosa mettere su FPGA deve misurare il
%  blocco che ci va davvero. I probe restano solo come riferimento diagnostico (quanto pesa il decode).
%
%  ⚠️ LUT-64 e' fissata: la scelta del decode era gia' stata presa (errore di approssimazione sotto la
%  soglia di quantizzazione fixed accettata, 0.028 -- document/DECODE_LUT_SWEEP.md). Non e' un asse.
  % ⚠️ Questa funzione vive in study_tradeoff/common/, ma deve girare nella cartella `matlab/` (dove
  % stanno build_hdl_variants, i sorgenti da inlinare e snn_variants/). `cd(fileparts(mfilename))`
  % portava in common/ e faceva fallire tutto con "build_hdl_variants is not found".
  % Si RISOLVE la posizione invece di assumerla: si chiede a MATLAB dov'e' build_hdl_variants.
  w = which('build_hdl_variants');
  assert(~isempty(w), ['build_hdl_variants non sul path: aggiungere la cartella matlab/ ' ...
                       'con addpath prima di chiamare gen_donatello_point']);
  here = fileparts(w);
  cd(here);

  if nargin < 2 || isempty(decVariant)
      error('gen_donatello_point:noVariant', ...
            ['decVariant OBBLIGATORIA (fused|p3|p5): un default silenzioso ha gia'' prodotto ' ...
             'esperimenti col decode sbagliato e numeri credibili.']);
  end
  % ⚠️ CACHE slprj: DIMOSTRATO che HDL Coder riusa la SNN gia' compilata e IGNORA il sorgente inlinato
  % cambiato. Prova: stesso swap a R5, con cache -> artefatto con pCm=276 (firma R9); senza cache ->
  % pCm=0 (firma R5). Il decode invece propagava, perche' sta nella chart riscritta. Metà del blocco
  % dalla configurazione chiesta, metà da quella precedente -> numeri credibili e sbagliati.
  if exist(fullfile(here,'slprj'),'dir'), rmdir(fullfile(here,'slprj'),'s'); end

  if nargin < 3 || isempty(snnSrc), snnSrc = 'snn_b2_fsm.m'; end
  if nargin < 4 || isempty(archStyle), archStyle = 'chart'; end
  fprintf('=== GEN: build_hdl_variants(''%s'', ''%s'', ''shared'', ''%s'') (cache azzerata) ===\n', ...
          decVariant, snnSrc, archStyle);
  build_hdl_variants(decVariant, snnSrc, 'shared', archStyle);

  fprintf('=== GEN: rtl_gen_dut(Donatello_LUT64) -> %s ===\n', outdir);
  rtl_gen_dut('Donatello_LUT64', outdir);

  % ⚠️ makehdl ANNIDA i .vhd in una sottocartella col nome del modello (<outdir>/rtlgen_mdl/): un
  % glob piatto non trova nulla. Prima versione di questo controllo stampava "GEN-OK 0 file" -- un
  % VERDE FALSO: dichiarava successo avendo trovato zero file. Ora la ricerca e' ricorsiva E il
  % cancello ASSERTA che ci sia il top: se manca, si ferma rumorosamente.
  d = dir(fullfile(outdir, '**', '*.vhd'));
  if isempty(d)
      error('gen_donatello_point:noVhdl', 'nessun .vhd prodotto sotto %s', outdir);
  end
  if ~any(strcmp({d.name}, 'Donatello_LUT64.vhd'))
      error('gen_donatello_point:noTop', ...
            'prodotti %d .vhd ma manca il top Donatello_LUT64.vhd sotto %s', numel(d), outdir);
  end
  fprintf('GEN-OK %d file .vhd sotto %s\n', numel(d), outdir);
  for k = 1:numel(d)
      fprintf('  %s (%d byte) in %s\n', d(k).name, d(k).bytes, d(k).folder);
  end
end
