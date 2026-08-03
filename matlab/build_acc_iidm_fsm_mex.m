function build_acc_iidm_fsm_mex()
%BUILD_ACC_IIDM_FSM_MEX  [SP4-M-FSM] Builda i MEX che servono a G2: fsm_step_mex (model FSM,
%  acc_iidm_fsm) e collect_step_mex (riferimento SP3, acc_iidm_open). Senza, G2 sul dataset intero
%  costerebbe ~47 min PER LATO in fi interpretato (il muro di Donatello).
%  I wrapper costruiscono acc_types('fixed') DENTRO (coder.const) -> il ramo reciproco-LUT (variante L,
%  acc_recip_lut) non viene compilato: con T passato come argomento, codegen fallisce con
%  "Expression could not be reduced to a constant" su acc_recip_lut.
  here = fileparts(mfilename('fullpath')); old = cd(here); c = onCleanup(@() cd(old)); %#ok<NASGU>
  args = {0, 0, 0, 0, zeros(5,1), true};
  fprintf('codegen fsm_step -> fsm_step_mex ...\n');
  codegen('fsm_step', '-args', args, '-o', 'fsm_step_mex');
  fprintf('codegen collect_step -> collect_step_mex ...\n');
  codegen('collect_step', '-args', args, '-nargout', 2, '-o', 'collect_step_mex');
  fprintf('MEX pronti: fsm_step_mex, collect_step_mex\n');
end
