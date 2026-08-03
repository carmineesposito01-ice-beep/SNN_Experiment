function extract_champion_algo(blockName)
%EXTRACT_CHAMPION_ALGO  Rigenera snn_champion_algo.m estraendo VERBATIM lo script della chart del blocco
%  (l'algoritmo self-contained: normalize + forward + decode) e rinominando la funzione entry
%  SNN -> snn_champion_algo. Cosi' il golden (snn_traj_champion) resta SEMPRE in sync col blocco: se il
%  blocco cambia (build_hdl_variants), si rigenera e il golden lo segue. NON committato (rigenerabile).
%
%  Perche' l'algoritmo INTERO e non solo la normalize: il blocco pilota il forward a INGRESSO TENUTO
%  (xn costante durante l'inferenza), mentre snn_traj_b2 lo pilota con ZERI -> divergono (misurato:
%  params a step 52). Solo l'algoritmo esatto guidato clock-per-clock come il blocco == il blocco.
  if nargin < 1, blockName = 'Donatello_Champion'; end
  here = fileparts(mfilename('fullpath'));
  if ~bdIsLoaded('snn_champions_lib'), load_system(fullfile(here,'snn_champions_lib.slx')); end
  c = sfroot().find('-isa','Stateflow.EMChart','Path',['snn_champions_lib/' blockName '/SNN']);
  assert(~isempty(c), 'chart %s/SNN non trovata', blockName);
  src = regexprep(c(1).Script, ...
        'function\s+\[v0,\s*T,\s*s0,\s*a,\s*b\]\s*=\s*SNN\s*\(', ...
        'function [v0, T, s0, a, b] = snn_champion_algo(', 'once');
  assert(contains(src,'function [v0, T, s0, a, b] = snn_champion_algo('), 'rinomina SNN fallita');
  fid = fopen(fullfile(here,'snn_champion_algo.m'),'w'); fprintf(fid,'%s\n', src); fclose(fid);
  fprintf('extract_champion_algo: snn_champion_algo.m rigenerato da %s (%d caratteri)\n', blockName, numel(src));
end
