function run_2d_round(tag)
%RUN_2D_ROUND  [B2.0-2d] Fase MATLAB di un round probe-and-pipeline sul path SNN->decode.
%  Rebuild dei blocchi HDL-ready da snn_b2_fsm/decode, gate bit-exact, gen VHDL del controllore per
%  la sintesi OOC L2 (Vivado space-free + parse RESULT/CRITPATH sono lo step bash a valle).
%
%  Gate (tutti devono passare o la funzione ABORTA prima della sintesi):
%    - G3/G4  : dentro build_hdl_variants (blocco == model/SP3 su 12 control-step).
%    - parity : run_b2_parity_dataset('Donatello') = 0/60000 -> RICOMPILA il MEX da snn_b2_fsm.m,
%               confronta il forward serializzato vs il core su 60 traj x 1000. E' il guardiano DURO
%               del core ristrutturato (HDL_PHASE §2.1: senza questo, 82,4% divergeva a gate verde).
%    - B-1    : run_rtl_validate_b = RTL FRESCO (rigenerato dal blocco corrente) == blocco su 3000.
%
%    run_2d_round('r2')
  if nargin < 1 || isempty(tag), tag = 'r2'; end
  here = fileparts(mfilename('fullpath'));
  addpath(here);
  setenv('PATH', ['C:\PROGRA~1\Git\bin;' getenv('PATH')]);   % xsim: bash->WSL rotto, forza Git Bash (SP4 §2b)

  fprintf('\n==== 2d %s: BUILD (rebuild blocchi da snn_b2_fsm) ====\n', tag);
  build_hdl_variants();

  fprintf('\n==== 2d %s: GATE parity 0/60000 (guardiano DURO del core) ====\n', tag);
  [~, nbs] = run_b2_parity_dataset('Donatello');
  assert(nbs == 0, '2d %s: parity FALLITO %d/60000 -> round NON bit-exact (STOP, niente sintesi)', tag, nbs);

  fprintf('\n==== 2d %s: GATE B-1 (RTL FRESCO == blocco) ====\n', tag);
  rd = fullfile(here, 'hdlsrc_donatello_acc_iidm_m_v');
  if exist(rd, 'dir'), rmdir(rd, 's'); end       % forza rigenerazione RTL dal blocco corrente (non riusare il .v stantio di R1)
  run_rtl_validate_b([1 7 23], 'reduced');

  fprintf('\n==== 2d %s: GEN VHDL controllore per OOC L2 ====\n', tag);
  probe_pipe_tanh({tag, 0, 'off', 'off'});       % source-driven: nessun attributo di pipeline

  fprintf('\n=== 2d %s: fase MATLAB OK -> VHDL in matlab/hdl_pipe/%s (ora sintesi OOC bash) ===\n', tag, tag);
end
