function idx = subset_diverse(mroot)
%SUBSET_DIVERSE  Subset diversificato di test_dataset.mat per il gate rapido di sviluppo ('smoke'):
%  1 traiettoria per ogni combinazione scenario x profilo presente + gli estremi di |dv| + >=1 con cut-in.
%  NB: i numeri RIPORTABILI sono quelli su tutte le 60 (prova e metriche sullo stesso perimetro).
  if nargin<1 || isempty(mroot)
    mroot = fullfile(fileparts(mfilename('fullpath')),'..','..','matlab');
  end
  ds = load(fullfile(mroot,'test_dataset.mat')); tr = ds.trajectories; N = numel(tr);
  key = strings(N,1); ci = false(N,1); dvmax = zeros(N,1);
  for t=1:N
    key(t) = string(tr{t}.scenario)+"|"+string(tr{t}.profile);
    c = tr{t}.cut_in; ci(t) = any(double(c(:))~=0);
    v = double(tr{t}.val); dvmax(t) = max(abs(v(3,:)));
  end
  [~,ia] = unique(key,'stable'); idx = ia(:).';
  [~,mx] = max(dvmax); [~,mn] = min(dvmax); idx = unique([idx mx mn]);
  if ~any(ci(idx)), idx = unique([idx find(ci,1)]); end
  fprintf('subset diversificato: %d traiettorie -> %s\n', numel(idx), mat2str(idx));
end
