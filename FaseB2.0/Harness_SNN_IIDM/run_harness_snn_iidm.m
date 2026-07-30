function run_harness_snn_iidm(mode)
%RUN_HARNESS_SNN_IIDM  ENTRY-POINT UNICO di T7a: rigenera TUTTO e salva i numeri su disco.
%
%  mode = 'smoke' (3 scenari: normale, cut-in, collisione) | 'full' (tutti i 99)
%
%  Prodotti (i numeri vivono negli ARTEFATTI, non nella console):
%    results/RESULTS.md        sintesi dei cancelli e delle metriche
%    results/t7_results.mat    strutture dei cancelli + configurazione misurata
%    results/metrics.json      le 31 metriche per scenario, RTL e oracolo
%
%  CATENA (l'ordine conta: l'RTL gira PRIMA, poi il blocco lo verifica sugli ingressi ricevuti):
%    1. cancello di parita' dell'oracolo (qz_cl_sim == simulate() canonico Python)
%    2. oracolo sui 99  -> sequenza accel per PLANT-PAR + baseline delle metriche
%    3. export degli scenari in .mem
%    4. PLANT-PAR: il plant del TB == qz_cl_sim, SENZA DUT
%    5. anello RTL in xsim: una simulazione per scenario
%    6. cancelli: T7-EXACT (RTL == BLOCCO sugli ingressi ricevuti), PARAM-RANGE, NO-REPEAT
%    7. metriche dal motore canonico Python + cancello duro T7-SAFE
  if nargin < 1 || isempty(mode), mode = 'smoke'; end
  here = fileparts(mfilename('fullpath'));
  root = fileparts(fileparts(here));
  addpath(fullfile(root,'matlab'), fullfile(root,'matlab','Quantizzation_Study'), here);
  switch mode
    case 'smoke', idx = [1 4 9];      % normale · con cut-in · che collide (perimetro DICHIARATO)
    case 'full',  idx = 1:99;
    otherwise, error('run_harness_snn_iidm: mode = ''smoke'' | ''full''');
  end
  WORK = 'C:/t7ver';                  % work-dir SENZA SPAZI (xsim/glob si spezzano sugli spazi)
  HDL  = 'C:/t7hdlv/rtlgen_mdl';      % VERILOG: un TB Verilog non puo' leggere segnali interni di un
  K = 600; HOLD_RTL = 600; HOLD_BLK = 700;   % DUT VHDL -> xelab CRASHA (HDL_PHASE §9.10bis)
  resdir = fullfile(here,'results'); if ~isfolder(resdir), mkdir(resdir); end
  t0 = tic;

  fprintf('\n== 1/7 cancello di parita'' dell''oracolo ==\n');
  qz_cl_parity_gate();

  fprintf('\n== 2/7 oracolo (%d scenari) ==\n', numel(idx));
  O = t7_oracle_cache(idx);

  fprintf('\n== 3/7 export degli scenari ==\n');
  t7_export_scenarios(WORK, idx, cellfun(@(o) o.series.a, O, 'uni', 0));

  fprintf('\n== 4/7 PLANT-PAR (plant del TB, SENZA DUT) ==\n');
  sh = @(s) strrep(s,'\','/');
  cmdP = sprintf('bash "%s" "%s" "%s" %d %d', ...
                 sh(fullfile(root,'FaseB2.0','common','rtl_run_plant_par.sh')), WORK, ...
                 sh(fullfile(here,'tb_plant_only.v')), K, numel(idx));
  [stP, outP] = system(cmdP); fprintf('%s\n', outP);
  assert(stP == 0 && contains(outP,'PLANTPAR-RUN-OK'), 'esecuzione di PLANT-PAR fallita');
  nPP = t7_plant_par(WORK, O, idx);
  assert(nPP == 0, ['PLANT-PAR FALLITO (%d disallineamenti): il plant del TB non riproduce qz_cl_sim. ' ...
                    'Correggere QUI, prima dell''anello live: altrimenti un difetto del plant si ' ...
                    'traveste da difetto del DUT.'], nPP);

  fprintf('\n== 5/7 anello RTL in xsim ==\n');
  cmdR = sprintf('bash "%s" "%s" "%s" "%s" %d %d %d', ...
                 sh(fullfile(root,'FaseB2.0','common','rtl_run_xsim_closed.sh')), WORK, HDL, ...
                 sh(fullfile(here,'tb_snn_iidm_closed.v')), K, HOLD_RTL, numel(idx));
  [stR, outR] = system(cmdR); fprintf('%s\n', outR);
  assert(stR == 0 && contains(outR,'RUNCLOSED-OK'), 'anello RTL fallito');

  fprintf('\n== 6/7 cancelli sull''RTL ==\n');
  V = t7_rtl_validate(WORK, idx, HOLD_BLK);
  assert(V.nExact == 0, 'T7-EXACT FALLITO: %d disallineamenti su %d', V.nExact, V.nTot);
  assert(V.nRange == 0, 'PARAM-RANGE FALLITO: %d control-step fuori dominio', V.nRange);
  sensitivity_t7(WORK, idx, HOLD_BLK);

  fprintf('\n== 7/7 metriche dal motore canonico ==\n');
  matf  = fullfile(resdir,'series.mat');
  jsonf = fullfile(resdir,'metrics.json');
  t7_series_to_mat(WORK, O, idx, matf);
  [st2, out2] = system(sprintf('cd /d "%s" && python "%s" "%s" "%s"', ...
                       root, fullfile(here,'t7_metrics.py'), matf, jsonf));
  fprintf('%s\n', out2);
  assert(st2 == 0, 'calcolo delle metriche fallito');

  M = jsondecode(fileread(jsonf)); S = M.x_summary;
  assert(S.coll_extra == 0, ...
    'T7-SAFE FALLITO: %d collisioni AGGIUNTIVE rispetto all''oracolo (scenari: %s)', ...
    S.coll_extra, mat2str(S.coll_extra_scenari));

  mins = toc(t0)/60;
  save(fullfile(resdir,'t7_results.mat'), 'V', 'S', 'nPP', 'idx', 'mode', ...
       'K', 'HOLD_RTL', 'HOLD_BLK', 'mins');
  t7_write_results(here, mode, idx, V, S, nPP, HOLD_RTL, HOLD_BLK, mins);
  fprintf('\nFATTO (%s, %.1f min). Numeri in results/RESULTS.md\n', mode, mins);
end
