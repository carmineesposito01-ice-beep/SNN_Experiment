function build_acciidm_m_golden()
%BUILD_ACCIIDM_M_GOLDEN  Prepara il golden FEDELE al controllore: estrae l'algoritmo (acciidm_m_algo.m)
%  e compila il MEX del driver clock-per-clock (acciidm_m_traj_mex). Idempotente. Gemello di
%  build_champion_golden per Harness B.
  extract_acciidm_m_algo();
  if isempty(which('acciidm_m_traj_mex'))
    valt = coder.typeof(zeros(4,1000),[4 Inf],[false true]);
    fprintf('build_acciidm_m_golden: codegen acciidm_m_traj...\n');
    evalc("codegen('acciidm_m_traj','-args',{valt, coder.typeof(0)},'-o','acciidm_m_traj_mex')");
  end
  assert(~isempty(which('acciidm_m_traj_mex')), 'codegen acciidm_m_traj_mex fallito');
  fprintf('build_acciidm_m_golden: golden fedele pronto (acciidm_m_traj_mex)\n');
end
