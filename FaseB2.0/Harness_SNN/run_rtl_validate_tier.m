function res = run_rtl_validate_tier(mode, trajList)
%RUN_RTL_VALIDATE_TIER  T6-EXACT: golden-da-blocco per traiettoria (in ROOT), UN xsim per traiettoria (la
%  DualPortRAM e' azzerata all'init della simulazione, come il golden), assert. mode 'reduced' (subset
%  diversificato) o 'full' (1:60). Cancelli: T6-EXACT (nMismatch==0) + LAT (< HOLD). Sensibilita: sensitivity_t6.m.
  here   = fileparts(mfilename('fullpath'));
  mroot  = fullfile(here,'..','..','matlab'); addpath(mroot); addpath(fullfile(here,'..','common'));
  ROOT   = 'D:/zbd_tier';
  hdlroot= fullfile(mroot,'hdlsrc_donatello_tier');
  hdlsrc = fullfile(hdlroot,'rtlgen_mdl');
  tb     = fullfile(here,'tb_tier_stream.v');
  runner = fullfile(here,'..','common','rtl_run_xsim.sh');
  fwd    = @(p) strrep(p,'\','/');
  if nargin<1||isempty(mode), mode='reduced'; end
  if nargin<2||isempty(trajList)
    if strcmp(mode,'full'), trajList = 1:60; else, trajList = subset_diverse(mroot); end
  end
  if ~exist(fullfile(hdlsrc,'Donatello_Tier.vhd'),'file')
    info = rtl_gen_dut('Donatello_Tier', hdlroot, 'VHDL', {'TIER','BALANCED','NFRAC','13'});
    hdlsrc = info.outdir;
  end
  tag = mode; HOLD = 500;
  % tutte le traiettorie stessa lunghezza (dataset-60: 1000) -> un solo K per il TB compilato una volta
  ds = load(fullfile(mroot,'test_dataset.mat'));
  Ks = arrayfun(@(t) size(ds.trajectories{t}.val,2), trajList);
  assert(all(Ks==Ks(1)), 'traiettorie con lunghezze diverse: %s', mat2str(Ks));
  K1 = Ks(1);
  % un .mem per traiettoria (il runner rifa xsim per traj -> RAM fresca all'init)
  for ti = 1:numel(trajList)
    tier_export_vectors(trajList(ti), sprintf('%s_%d', tag, ti), ROOT);
  end
  cmd = sprintf('bash "%s" "%s" "%s" "%s" %d %d %d stim_%s gold_%s', ...
                fwd(runner), ROOT, fwd(hdlsrc), fwd(tb), K1, HOLD, numel(trajList), tag, tag);
  [~, out] = system(cmd);
  tok = regexp(out, 'RTLRES nMismatch=(\d+) n=(\d+)', 'tokens', 'once');
  assert(~isempty(tok), 'xsim non ha prodotto RTLRES. Output:\n%s', out);
  res = struct('nMismatch',str2double(tok{1}), 'n',str2double(tok{2}), 'K',K1, 'traj',numel(trajList));
  lt = regexp(out,'LAT_RTL (\d+)','tokens','once'); res.lat = str2double(lt{1});
  % --- LAT ---
  assert(~isempty(lt) && res.lat>0 && res.lat<HOLD, ...
         'LAT FALLITO: latenza RTL=%d, HOLD=%d (campiono PRIMA che l''uscita sia pronta).', res.lat, HOLD);
  fprintf('LAT: latenza RTL misurata = %d clock (< HOLD=%d) OK\n', res.lat, HOLD);
  % --- T6-EXACT ---
  fprintf('T6-EXACT [%s]: nMismatch = %d / %d  (%d traj x %d control-step x 5 param; lat=%d)\n', ...
          mode, res.nMismatch, res.n, res.traj, K1, res.lat);
  assert(res.nMismatch==0, ...
         'T6-EXACT FALLITO: il VHDL del Tier NON riproduce il blocco (%d/%d) -> non bit-exact RTL.', res.nMismatch, res.n);
  fprintf('=== T6-EXACT PASSATO [%s]: Donatello_Tier RTL == blocco su %d/%d ===\n', mode, res.n, res.n);
end

function idx = subset_diverse(mroot)
% 1 traj per combinazione scenario x profilo + estremi di dv + >=1 con cut-in
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
