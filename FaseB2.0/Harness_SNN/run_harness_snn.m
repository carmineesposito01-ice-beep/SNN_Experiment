function R = run_harness_snn(mode)
%RUN_HARNESS_SNN  Entry-point UNICO dell'Harness_SNN (Fase B2.0 T6a): esegue l'intera catena e salva i risultati.
%
%  Uso:  matlab -sd <questa cartella> -batch "run_harness_snn"           % 'full' (i 60) = numeri RIPORTABILI
%        matlab -sd <questa cartella> -batch "run_harness_snn('smoke')"  % gate rapido di sviluppo (subset)
%
%  Catena: VHDL (se assente) -> golden in cache (UNA volta) -> T6-EXACT + LAT -> sensibilita -> metriche -> results/.
%  Prova e metriche girano sugli STESSI dati (stessa cache, stessa lista di traiettorie).
%  Prodotti: results/harness_snn_results.mat + results/RESULTS.md. Runtime 'full' ~75 min, 'smoke' ~15 min.
  if nargin<1 || isempty(mode), mode = 'full'; end
  here = fileparts(mfilename('fullpath'));
  addpath(fullfile(here,'..','..','matlab')); addpath(fullfile(here,'..','common'));
  outdir = fullfile(here,'results'); if ~exist(outdir,'dir'), mkdir(outdir); end
  t0 = tic;
  fprintf('=== HARNESS_SNN [%s] — Donatello_Tier@BALANCED ===\n', mode);

  % 1) lista traiettorie + golden in cache (scaldata QUI: gli export per-traiettoria devono trovare HIT,
  %    altrimenti ricalcolerebbero e sovrascriverebbero la cache una traiettoria alla volta)
  if strcmp(mode,'full'), trajList = 1:60; else, trajList = subset_diverse(); end
  [~, gmeta] = tier_golden_cache(trajList);

  % 2) T6-EXACT + LAT (una simulazione xsim per traiettoria: la DualPortRAM si azzera solo all'init)
  rtl = run_rtl_validate_tier(mode, trajList);

  % 3) sensibilita: il cancello deve poter fallire (1 LSB corrotto -> nMismatch>=1)
  sens = sensitivity_t6();

  % 4) metriche di stima sugli STESSI dati del confronto RTL
  M = tier_rtl_metrics(rtl.trajListUsed);

  R = struct('mode',mode, 'rtl',rtl, 'sens',sens, 'metrics',M, 'golden',gmeta, ...
             'when',char(datetime('now','Format','yyyy-MM-dd HH:mm:ss')), 'secs',toc(t0));
  save(fullfile(outdir,'harness_snn_results.mat'), '-struct', 'R');
  write_results_md(fullfile(outdir,'RESULTS.md'), R);
  fprintf('\n=== HARNESS_SNN COMPLETATO in %.1f min -> results/ ===\n', R.secs/60);
end

function write_results_md(f, R)
  fid = fopen(f,'w');
  w = @(varargin) fprintf(fid, varargin{:});
  c = R.golden.cfg;
  w('# Harness_SNN — risultati (Fase B2.0 · T6a)\n\n');
  w('Generato da `run_harness_snn(''%s'')` il %s — runtime %.1f min.\n', R.mode, R.when, R.secs/60);
  w('Rigenerabile con **un comando** (vedi README).\n\n');
  w('## Configurazione misurata\n\n| parametro | valore |\n|---|---|\n');
  w('| blocco | `%s` @ TIER=%s, NFRAC=%d |\n', c.block, c.tier, c.nfrac_param);
  w('| ingressi | `fixdt(1,32,%d)` · hold %d clock |\n', c.nfrac_in, c.hold);
  w('| dataset | `%s` — %d traiettorie × %d control-step |\n', c.dataset, numel(R.rtl.trajListUsed), R.rtl.K);
  w('| latenza blocco (misurata) | %d clock |\n', R.golden.lat);
  w('| golden | dal BLOCCO stesso (oracolo), calcolato una volta e condiviso da RTL e metriche |\n\n');
  w('## Cancelli\n\n| cancello | esito | numeri |\n|---|---|---|\n');
  w('| **T6-EXACT** — RTL 5 param == blocco | %s | nMismatch **%d / %d** (%d traj × %d step × 5 param) |\n', ...
    pf(R.rtl.nMismatch==0), R.rtl.nMismatch, R.rtl.n, R.rtl.traj, R.rtl.K);
  w('| **LAT** — latenza misurata < HOLD | %s | %d clock (HOLD %d) |\n', ...
    pf(R.rtl.lat>0 && R.rtl.lat<c.hold), R.rtl.lat, c.hold);
  w('| **Sensibilità** — 1 LSB corrotto | %s | nMismatch %d (atteso ≥1) |\n', pf(R.sens>=1), R.sens);
  w('| **PORT-TYPE** | %s | coperto da T6-EXACT (tipo errato ⇒ mismatch sistematico) |\n\n', pf(R.rtl.nMismatch==0));
  w('## Accuratezza di stima (versione FPGA == blocco)\n\n| param | max | p99 |\n|---|---|---|\n');
  nm = fieldnames(R.metrics);
  for i=1:numel(nm), w('| `%s` | %.4g | %.4g |\n', nm{i}, R.metrics.(nm{i}).max, R.metrics.(nm{i}).p99); end
  w('\n`v0` alto = **identificabilità** (osservabile solo a flusso libero), non difetto RTL.\n');
  w('La qualità car-following è il closed-loop (T7).\n');
  fclose(fid);
end

function s = pf(ok)
  if ok, s = '**PASS**'; else, s = '**FAIL**'; end
end
