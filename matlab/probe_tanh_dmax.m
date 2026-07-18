function M = probe_tanh_dmax(tanhFn, trajList)
%PROBE_TANH_DMAX  [B2.0-2b] dmax a livello ACCEL della variante tanh vs il nativo, sul dataset.
%  Riusa i forward SNN + fasi (come probe_dd_range); per ogni step confronta iidm_final(st, tanh(st.dd))
%  con iidm_final(st, tanhFn(st.dd)). tanhFn = handle (es. @tanh_lut_full). iidm_final e' single-source.
  if nargin<2||isempty(trajList), trajList=1:20; end
  here=fileparts(mfilename('fullpath'));
  d=load(fullfile(here,'champions_export.mat')); ch=d.champions; if iscell(ch), ch=[ch{:}]; end
  c=ch(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'),ch),1));
  nrm=double(c.norm(:)); Tp=numerictype(1,21,13);
  gen_b2_rom('Donatello'); clear snn_traj_b2_mex; rehash;
  valt=coder.typeof(zeros(4,1000),[4 Inf],[false true]);
  evalc("codegen('snn_traj_b2','-args',{valt,coder.typeof(zeros(4,1))},'-o','snn_traj_b2_mex')");
  ds=load(fullfile(here,'test_dataset.mat')); tr=ds.trajectories; T=acc_types('fixed');
  err=[];
  for t=trajList(:).'
    valq=fi(double(tr{t}.val),1,32,20); R=double(snn_traj_b2_mex(tr{t}.val,nrm)); K=size(R,1);
    alf=cast(0,'like',T.acc); vlp=cast(valq(4,1),'like',T.st);
    for k=1:K
      p=snn_decode_lut(fi(R(k,:).',Tp),64);
      [st,alf,vlp]=iidm_prep(valq(1,k),valq(2,k),valq(3,k),valq(4,k),p(:),k==1,alf,vlp);
      for kk=1:5, [nu,de]=iidm_nd(kk,st); q=fsm_div(nu,de); st=iidm_use(kk,q,st); end
      a_nat=double(iidm_final(st, tanh(st.dd)));
      a_var=double(iidm_final(st, tanhFn(st.dd)));
      err=[err; abs(a_nat-a_var)]; %#ok<AGROW>
    end
  end
  M=struct('max',max(err),'p99',prctile(err,99),'p999',prctile(err,99.9),'mean',mean(err),'n',numel(err));
  fprintf('dmax_accel [%s]: max=%.6g p99.9=%.6g p99=%.6g mean=%.6g  (n=%d)\n', ...
          func2str(tanhFn), M.max, M.p999, M.p99, M.mean, M.n);
end
