function extract_acciidm_m_algo()
%EXTRACT_ACCIIDM_M_ALGO  Rigenera acciidm_m_algo.m estraendo VERBATIM lo script della chart IIDM_CTRL del
%  blocco Donatello_ACC_IIDM_M (algoritmo self-contained: normalize + SNN + decode + IIDM -> accel) e
%  rinominando l'entry IIDM_CTRL -> acciidm_m_algo. Gemello di extract_champion_algo per il controllore.
%  Stesso motivo di M1: il golden fedele = l'algoritmo esatto guidato clock-per-clock a ingresso tenuto,
%  non il riferimento (che diverge per la local_normalize fixed + il pilotaggio a zeri). NON committato.
  here = fileparts(mfilename('fullpath'));
  if ~bdIsLoaded('snn_champions_lib'), load_system(fullfile(here,'snn_champions_lib.slx')); end
  c = sfroot().find('-isa','Stateflow.EMChart','Path','snn_champions_lib/Donatello_ACC_IIDM_M/IIDM_CTRL');
  assert(~isempty(c), 'chart Donatello_ACC_IIDM_M/IIDM_CTRL non trovata');
  src = regexprep(c(1).Script, 'function\s+accel\s*=\s*IIDM_CTRL\s*\(', ...
        'function accel = acciidm_m_algo(', 'once');
  assert(contains(src,'function accel = acciidm_m_algo('), 'rinomina IIDM_CTRL fallita');
  fid = fopen(fullfile(here,'acciidm_m_algo.m'),'w'); fprintf(fid,'%s\n', src); fclose(fid);
  fprintf('extract_acciidm_m_algo: acciidm_m_algo.m rigenerato (%d caratteri)\n', numel(src));
end
