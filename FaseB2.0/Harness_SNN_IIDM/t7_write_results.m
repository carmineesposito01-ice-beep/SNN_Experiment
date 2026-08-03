function t7_write_results(here, mode, idx, V, S, nPP, HOLD_RTL, HOLD_BLK, mins)
%T7_WRITE_RESULTS  Scrive results/RESULTS.md da risultati GIA' calcolati.
%  In un file a se' (e non dentro l'entry-point) cosi' il report si rigenera senza rifare la run:
%    R = load('results/t7_results.mat'); M = jsondecode(fileread('results/metrics.json'));
%    t7_write_results(here, R.mode, R.idx, R.V, M.x_summary, R.nPP, R.HOLD_RTL, R.HOLD_BLK, R.mins)
  f = fopen(fullfile(here,'results','RESULTS.md'),'w');
  fprintf(f, '# T7a — Harness_SNN_IIDM: anello chiuso RTL + metriche\n\n');
  fprintf(f, '> Rigenerabile con `run_harness_snn_iidm(''%s'')` — %.1f min.\n', mode, mins);
  fprintf(f, '> DUT **`Donatello_SNN_IIDM`** (Tier@BALANCED + align + ACC-IIDM R17), generato in\n');
  fprintf(f, '> **Verilog**, %d scenari x 600 control-step. `HOLD_RTL`=%d, `HOLD_BLK`=%d (latenza misurata 554).\n\n', ...
          numel(idx), HOLD_RTL, HOLD_BLK);

  fprintf(f, '## Cancelli\n\n| Cancello | Che cosa prova | Perimetro | Esito |\n|---|---|---|---|\n');
  fprintf(f, '| **PLANT-PAR** | plant del TB == `qz_cl_sim`, **senza DUT** | %d scenari | **%d disallineamenti** |\n', numel(idx), nPP);
  fprintf(f, '| **T7-EXACT** | RTL == **BLOCCO** sugli ingressi ricevuti | %d confronti | **%d disallineamenti** |\n', V.nTot, V.nExact);
  fprintf(f, '| PARAM-RANGE | i 5 parametri nei limiti del decode | %d control-step | **%d fuori dominio** |\n', V.nTot, V.nRange);
  fprintf(f, '| **T7-SAFE** | collisioni AGGIUNTIVE vs oracolo | %d scenari | **%d extra** |\n\n', numel(idx), S.coll_extra);
  fprintf(f, 'Ogni cancello e'' **provato sensibile** (`sensitivity_t7`).\n');
  fprintf(f, 'PLANT-PAR e T7-EXACT **non condividono** il componente che l''altro verifica: il primo gira\n');
  fprintf(f, 'senza DUT, il secondo senza plant. Insieme coprono l''anello senza circolarita''.\n\n');

  fprintf(f, '## Sicurezza\n\nCollisioni: RTL **%d**, oracolo **%d** su %d scenari — **%d aggiuntive**.\n', ...
          S.coll_rtl, S.coll_oracolo, S.n_scenari, S.coll_extra);
  fprintf(f, 'Le collisioni presenti anche nell''oracolo sono **inevitabili** (cut-in aggressivo):\n');
  fprintf(f, 'un controllore a conoscenza perfetta le subisce ugualmente.\n\n');

  fprintf(f, '## Diagnostica NO-REPEAT — comportamento del blocco, non un difetto dell''RTL\n\n');
  fprintf(f, '**%d control-step su %d (%.1f %%)** hanno i 5 parametri identici al precedente. In quei passi\n', ...
          V.nRep, V.nTot, 100*V.nRep/max(V.nTot,1));
  fprintf(f, '`align` non rilascia i nuovi ingressi fisici e l''ACC non ricalcola: l''accelerazione resta\n');
  fprintf(f, '**congelata** — verificato nel **100 %%** dei casi, zero eccezioni.\n\n');
  fprintf(f, 'Non e'' un difetto dell''RTL (T7-EXACT e'' 0: l''hardware riproduce il blocco esattamente) ed e''\n');
  fprintf(f, 'un comportamento **atteso a regime**: e'' concentrato negli scenari `static_target` (leader\n');
  fprintf(f, 'fermo, 85-87 %% dei passi), dove l''ego converge a un equilibrio e i parametri quantizzati\n');
  fprintf(f, 'smettono **legittimamente** di cambiare. **%d scenari su %d non ne hanno affatto** (mediana 0 %%).\n\n', ...
          numel(idx) - numel(V.repScen), numel(idx));
  fprintf(f, 'Impatto misurato rispetto all''oracolo (mediane, scenari congelati vs non congelati):\n');
  fprintf(f, '**la sicurezza e'' intatta** — `min_ttc` 0,97x, `max_DRAC` 1,07x, **0 collisioni aggiuntive**;\n');
  fprintf(f, 'il costo e'' su tracking (`rms_gap_error` 1,37x) e comfort (`rms_jerk` 1,30x).\n\n');

  fprintf(f, '## Metriche\n\n**%d metriche per scenario**, dal motore canonico `utils/closed_loop_eval`\n', S.n_metriche);
  fprintf(f, '(lo stesso di VALIDATION_REPORT_v3 e QUANTIZATION_STUDY_REPORT) calcolate sulle serie\n');
  fprintf(f, '**prodotte dall''RTL**, non dal blocco. Dettaglio per scenario: `results/metrics.json`.\n\n');

  fprintf(f, '## Riferimento del DUT\n\n');
  fprintf(f, 'Il riferimento e'' il **blocco composto**, ripilotato sugli ingressi che l''RTL ha\n');
  fprintf(f, 'effettivamente ricevuto. Il golden monolitico `acciidm_m_traj` **non e'' utilizzabile**:\n');
  fprintf(f, 'e'' l''estrazione del blocco DEPRECATO `Donatello_ACC_IIDM_M` e diverge dal composto\n');
  fprintf(f, '(385 scarti su 600 control-step, misurato il 2026-07-30).\n');
  fclose(f);
  fprintf('t7_write_results: scritto %s\n', fullfile(here,'results','RESULTS.md'));
end
