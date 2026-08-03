function run_iidm_round(tag, hold)
%RUN_IIDM_ROUND  [Studio IIDM] Fase MATLAB di un round: rebuild + cancelli bit-exact + gen VHDL per l'OOC.
%  Cancelli: G3/G4 (blocco == model == SP3) + parity 0/60000 (SNN invariata) + B-1 0/3000 (RTL FRESCO
%  == blocco). La sintesi OOC (space-free) e il parse RESULT/CRITPATH sono lo step bash a valle.
%
%  G2 (model == acc_iidm_open su 60k) NON e' qui: in questo studio il model e le funzioni-fase NON
%  cambiano -- cambia solo CHI fa la divisione. Si esegue una tantum (piano T4 Step 3).
%
%  ⚠️ `hold` = clock tenuti per control-step. DEVE superare la LATENZA del blocco (stampata da G4), o i
%     cancelli falliscono su matematica CORRETTA. Con il divisore pipelinato la latenza e' 584 -> 900.
%     Ogni round che aggiunge pipeline ALZA la latenza: rileggerla da G4 e alzare `hold` se serve.
%
%    run_iidm_round('r1', 900)
  if nargin < 1 || isempty(tag),  tag  = 'r1'; end
  if nargin < 2 || isempty(hold), hold = 900; end
  here = fileparts(mfilename('fullpath')); addpath(here);
  setenv('PATH', ['C:\PROGRA~1\Git\bin;' getenv('PATH')]);   % xsim: bash->WSL rotto (SP4 §Studio 2b)

  fprintf('\n==== IIDM %s: BUILD + G3/G4 (hold=%d) ====\n', tag, hold);
  build_hdl_variants();
  d34 = run_block_acciidm_m_test(12, 1, hold);
  assert(d34 == 0, 'G3/G4 FALLITO: dmax=%g', d34);

  fprintf('\n==== IIDM %s: parity SNN 0/60000 (la rete non deve muoversi) ====\n', tag);
  [~, nbs] = run_b2_parity_dataset('Donatello');
  assert(nbs == 0, 'parity FALLITO: %d/60000 control-step divergenti', nbs);

  fprintf('\n==== IIDM %s: B-1 (RTL FRESCO == blocco) ====\n', tag);
  rd = fullfile(here, 'hdlsrc_donatello_acc_iidm_m_v');
  if exist(rd, 'dir'), rmdir(rd, 's'); end     % forza la rigenerazione: mai riusare il .v stantio
  run_rtl_validate_b([1 7 23], 'reduced', hold);

  fprintf('\n==== IIDM %s: GEN VHDL per la sintesi OOC ====\n', tag);
  probe_pipe_tanh({tag, 0, 'off', 'off'});     % source-driven: nessun attributo di pipeline
  fprintf('\n=== IIDM %s: fase MATLAB OK -> matlab/hdl_pipe/%s (ora sintesi OOC) ===\n', tag, tag);
end
