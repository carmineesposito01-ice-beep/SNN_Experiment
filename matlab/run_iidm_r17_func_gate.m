function run_iidm_r17_func_gate(nSamples, L)
%RUN_IIDM_R17_FUNC_GATE  Cancello FUNZIONALE della chart standalone R17: streaming (ingresso tenuto L clock
%  per inferenza, l'IIDM time-mux ci mette ~150) == acc_iidm_open(...,acc_types('fixed',8)), dmax=0 su
%  traiettoria vera (l'OU ha memoria: campioni consecutivi). Prova che togliere la SNN dalla chart M R17
%  non ha toccato la matematica IIDM.
  if nargin<1 || isempty(nSamples), nSamples=25; end
  if nargin<2 || isempty(L), L=400; end
  here=fileparts(mfilename('fullpath')); addpath(here);
  code = iidm_r17_chart_code();
  td=fullfile(tempdir,'iidm_r17_func'); if exist(td,'dir'), rmdir(td,'s'); end; mkdir(td);
  fid=fopen(fullfile(td,'ACC_IIDM.m'),'w'); fwrite(fid,code); fclose(fid);

  ds=load(fullfile(here,'test_dataset.mat')); tr=ds.trajectories;
  val=double(tr{1}.val); p=tr{1}.gt_params(:);
  N=min(nSamples, size(val,2));

  addpath(td); clear ACC_IIDM;
  aC=zeros(N,1);
  for k=1:N
    ak=0;
    for c=1:L
      ak = ACC_IIDM(val(1,k),val(2,k),val(3,k),val(4,k), p(1),p(2),p(3),p(4),p(5));
    end
    aC(k)=ak;
  end
  rmpath(td);

  clear acc_iidm_open; Tf=acc_types('fixed',8); aR=zeros(N,1);
  for k=1:N, aR(k)=double(acc_iidm_open(val(1,k),val(2,k),val(3,k),val(4,k), p, k==1, Tf)); end

  dmax=max(abs(aC-aR));
  fprintf('R17 chart (streaming, L=%d) vs acc_iidm_open@8: dmax = %.4g su %d campioni\n', L, dmax, N);
  fprintf('   chart      open@8\n'); disp([aC(1:min(8,N)) aR(1:min(8,N))]);
  assert(dmax==0, 'R17 chart != acc_iidm_open@8 (dmax=%.4g)', dmax);
  fprintf('=== R17 chart FUNZIONALE OK (dmax=0) ===\n');
end
