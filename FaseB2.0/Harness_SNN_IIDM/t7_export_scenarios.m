function n = t7_export_scenarios(outdir, idx, accelCell)
%T7_EXPORT_SCENARIOS  Scrive, per ogni scenario, i .mem che i testbench di T7a leggono:
%    scen_<i>.mem : K righe da 1 double (v_leader), bit pattern IEEE-754 in esadecimale a 64 bit
%    init_<i>.mem : 4 righe  [s_init; v_init; cut_k (0 = nessun cut-in); cut_gap]
%    acc_<i>.mem  : K righe di accel (double) -- SOLO per PLANT-PAR, che pilota il plant SENZA DUT
%
%  outdir     : work-dir SENZA SPAZI (il repo sta sotto ".../1.Reti Neurali/...": xsim/glob si spezzano)
%  idx        : indici degli scenari in test_dataset_exhaustive.mat (1..99)
%  accelCell  : cell{numel(idx)} di sequenze accel, oppure [] (allora acc_<i>.mem non viene scritto)
%
%  I file sono numerati 1..numel(idx) nell'ORDINE di idx, non con l'indice dello scenario: i runner
%  iterano su 1..NSCEN. La corrispondenza sta in idx, che l'entry-point salva nei risultati.
  if ~exist(outdir,'dir'), mkdir(outdir); end
  here = fileparts(mfilename('fullpath'));
  ml   = fullfile(here,'..','..','matlab');
  ds = load(fullfile(ml,'Quantizzation_Study','test_dataset_exhaustive.mat'));
  tr = ds.trajectories;
  assert(iscell(tr), 'test_dataset_exhaustive.trajectories: atteso cell array');
  if ~isempty(accelCell)
    assert(numel(accelCell) == numel(idx), ...
           'accelCell ha %d elementi ma idx ne ha %d', numel(accelCell), numel(idx));
  end
  n = 0;
  for j = 1:numel(idx)
    t = tr{idx(j)};
    wr(fullfile(outdir,sprintf('scen_%d.mem',j)), double(t.v_leader(:)));
    if isempty(t.cut_in), ck = 0; cg = 0; else, ck = t.cut_in(1); cg = t.cut_in(2); end
    wr(fullfile(outdir,sprintf('init_%d.mem',j)), ...
       [double(t.s_init); double(t.v_init); double(ck); double(cg)]);
    if ~isempty(accelCell)
      wr(fullfile(outdir,sprintf('acc_%d.mem',j)), double(accelCell{j}(:)));
    end
    n = n + 1;
  end
  fprintf('t7_export_scenarios: %d scenari in %s (acc: %d)\n', n, outdir, ~isempty(accelCell));
end

function wr(path, x)
% double -> 16 cifre esadecimali (bit pattern IEEE-754): $readmemh + $bitstoreal lo rileggono esatto.
  f = fopen(path,'w');
  assert(f > 0, 'impossibile scrivere %s', path);
  for i = 1:numel(x)
    fprintf(f, '%016s\n', lower(dec2hex(typecast(double(x(i)),'uint64'), 16)));
  end
  fclose(f);
end
