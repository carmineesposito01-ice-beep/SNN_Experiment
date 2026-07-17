function rtl_export_vectors(harness, trajList, tag, outdir)
%RTL_EXPORT_VECTORS  Scrive stim/gold .mem + meta per la validazione RTL, dal riferimento MEX veloce.
%  harness 'snn'  -> gold = 5 param IDM (Q7.13, 21b) di Donatello_Champion (rif: snn_decode_lut(.,64)).
%  harness 'ctrl' -> gold = accel (Q4.8, 13b) di Donatello_ACC_IIDM_M (rif: collect_step_mex). [Harness B]
%
%  Il valore scritto e' lo STORED INTEGER (complemento a 2) mascherato alla larghezza della porta, via
%  typecast int32->uint32. NB: `uint32(x)` di un negativo SATURA a 0 in MATLAB -> falsi mismatch; qui
%  si reinterpretano i bit (typecast), non si converte il valore.
  here = fileparts(mfilename('fullpath'));
  assert(any(strcmp(harness,{'snn','ctrl'})), 'harness: ''snn'' o ''ctrl''');
  if ~exist(outdir,'dir'), mkdir(outdir); end
  ds = load(fullfile(here,'test_dataset.mat')); tr = ds.trajectories;
  d  = load(fullfile(here,'champions_export.mat')); ch = d.champions; if iscell(ch), ch = [ch{:}]; end
  c  = ch(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'), ch), 1));
  W  = champ_weights(c); Tp = numerictype(1,21,13);
  if strcmp(harness,'ctrl')
    assert(~isempty(which('collect_step_mex')), 'MEX mancante: build_acc_iidm_fsm_mex');
  end
  fs = fopen(fullfile(outdir,['stim_' tag '.mem']),'w');
  fg = fopen(fullfile(outdir,['gold_' tag '.mem']),'w');
  K = 0;
  for t = trajList(:).'
    R   = double(snn_traj_fixed_r16_mex(tr{t}.val, W));
    val = fi(double(tr{t}.val), 1, 32, 20);              % la quantizzazione che vede il blocco
    if strcmp(harness,'ctrl'), clear collect_step_mex; end   % stato OU pulito a inizio traiettoria
    for k = 1:size(val,2)
      for j = 1:4
        fprintf(fs, '%08X\n', typecast(int32(storedInteger(val(j,k))), 'uint32'));
      end
      p = snn_decode_lut(fi(R(k,:).', Tp), 64);          % 5x1 Q7.13
      if strcmp(harness,'snn')
        for i = 1:5
          fprintf(fg, '%06X\n', bitand(typecast(int32(storedInteger(p(i))),'uint32'), uint32(2^21-1)));
        end
      else
        a  = collect_step_mex(double(val(1,k)),double(val(2,k)),double(val(3,k)),double(val(4,k)),double(p),k==1);
        af = fi(a, 1, 13, 8);
        fprintf(fg, '%04X\n', bitand(typecast(int32(storedInteger(af)),'uint32'), uint32(2^13-1)));
      end
      K = K + 1;
    end
  end
  fclose(fs); fclose(fg);
  save(fullfile(outdir,['meta_' tag '.mat']), 'K', 'trajList', 'harness');
  fprintf('rtl_export_vectors(%s): %d control-step su %d traiettorie -> %s\n', harness, K, numel(trajList), outdir);
end
