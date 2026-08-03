function run_milestone_hdl_gates()
%RUN_MILESTONE_HDL_GATES  HDL-ready + self-contained per i blocchi HDL della libreria milestone (esclusi i
%  4 Campioni double, che sono comportamentali). Ogni caso: SOLO il .slx in cartella isolata, matlab/ fuori
%  dal path, makehdl -> VHDL generato = self-contained e HDL-ready DIMOSTRATO (non promesso).
%    Donatello_LUT  (default N=64, + variante N=16) : run_block_hdl_gate, DualPortRAM = time-mux
%    Donatello_Tier (default BALANCED/nfrac13)      : run_block_hdl_gate, DualPortRAM
%    Donatello_ACC_IIDM_M (controllore R17 completo) : run_block_hdl_gate, DualPortRAM
%    ACC-IIDM (IIDM R17 nativo, senza SNN)           : run_acc_iidm_gate, no DualPortRAM
  cases = { 'Donatello_LUT (N=64)',    @() run_block_hdl_gate('Donatello_LUT');
            'Donatello_LUT (N=16)',    @() run_block_hdl_gate('Donatello_LUT', {'NLUT','16'});
            'Donatello_Tier (BAL/13)', @() run_block_hdl_gate('Donatello_Tier');
            'Donatello_ACC_IIDM_M',    @() run_block_hdl_gate('Donatello_ACC_IIDM_M');
            'ACC-IIDM',                @() run_acc_iidm_gate() };
  res = cell(size(cases,1),2); allok = true;
  for i = 1:size(cases,1)
    fprintf('\n---- gate %d/%d: %s ----\n', i, size(cases,1), cases{i,1});
    try
      ok = cases{i,2}(); if isempty(ok), ok = true; end
    catch ME
      fprintf('!! %s FALLITO: %s\n', cases{i,1}, ME.message); ok = false;
    end
    res{i,1} = cases{i,1}; res{i,2} = ok; allok = allok && ok;
  end
  fprintf('\n=== HDL-READY / SELF-CONTAINED (milestone) ===\n');
  for i = 1:size(res,1), fprintf('  %-26s %s\n', res{i,1}, ternp(res{i,2})); end
  assert(allok, 'qualche blocco NON e'' HDL-ready/self-contained (vedi sopra)');
  fprintf('=== TUTTI I BLOCCHI HDL DELLA MILESTONE SONO HDL-READY E SELF-CONTAINED ===\n');
end

function s = ternp(p), if p, s = 'PASS'; else, s = 'FAIL'; end, end
