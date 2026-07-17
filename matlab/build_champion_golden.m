function build_champion_golden()
%BUILD_CHAMPION_GOLDEN  Prepara il golden FEDELE al blocco: estrae l'algoritmo (snn_champion_algo.m) e
%  compila il MEX del driver clock-per-clock (snn_traj_champion_mex). Da chiamare prima di generare i
%  vettori 'snn' se il MEX manca. Idempotente.
  here = fileparts(mfilename('fullpath'));
  extract_champion_algo('Donatello_Champion');
  if isempty(which('snn_traj_champion_mex'))
    valt = coder.typeof(zeros(4,1000),[4 Inf],[false true]);
    fprintf('build_champion_golden: codegen snn_traj_champion...\n');
    evalc("codegen('snn_traj_champion','-args',{valt, coder.typeof(0)},'-o','snn_traj_champion_mex')");
  end
  assert(~isempty(which('snn_traj_champion_mex')), 'codegen snn_traj_champion_mex fallito');
  fprintf('build_champion_golden: golden fedele pronto (snn_traj_champion_mex)\n');
end
