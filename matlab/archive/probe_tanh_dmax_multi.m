function probe_tanh_dmax_multi(trajList)
%PROBE_TANH_DMAX_MULTI  [B2.0-2b] dmax accel di PIU' varianti tanh vs nativo, in UN passaggio: le fasi
%  (iidm_prep/nd/use/fsm_div) + il forward SNN girano UNA volta sola per step, poi si valutano tutte le
%  varianti su `st`. Molto piu' veloce di N chiamate a probe_tanh_dmax. Metrica = |accel_var - accel_nativo|.
  if nargin<1||isempty(trajList), trajList=1:20; end
  here=fileparts(mfilename('fullpath'));
  d=load(fullfile(here,'champions_export.mat')); ch=d.champions; if iscell(ch), ch=[ch{:}]; end
  c=ch(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'),ch),1));
  nrm=double(c.norm(:)); Tp=numerictype(1,21,13);
  gen_b2_rom('Donatello'); clear snn_traj_b2_mex; rehash;
  valt=coder.typeof(zeros(4,1000),[4 Inf],[false true]);
  evalc("codegen('snn_traj_b2','-args',{valt,coder.typeof(zeros(4,1))},'-o','snn_traj_b2_mex')");
  ds=load(fullfile(here,'test_dataset.mat')); tr=ds.trajectories; T=acc_types('fixed');
  fns={@tanh_lut_interp,@tanh_poly,@tanh_cordic}; nm={'interp','poly','cordic'}; nf=numel(fns);
  err=[];
  for t=trajList(:).'
    valq=fi(double(tr{t}.val),1,32,20); R=double(snn_traj_b2_mex(tr{t}.val,nrm)); K=size(R,1);
    alf=cast(0,'like',T.acc); vlp=cast(valq(4,1),'like',T.st);
    e=zeros(K,nf);
    for k=1:K
      p=snn_decode_lut(fi(R(k,:).',Tp),64);
      [st,alf,vlp]=iidm_prep(valq(1,k),valq(2,k),valq(3,k),valq(4,k),p(:),k==1,alf,vlp);
      for kk=1:5, [nu,de]=iidm_nd(kk,st); q=fsm_div(nu,de); st=iidm_use(kk,q,st); end
      an=double(iidm_final(st, tanh(st.dd)));
      for j=1:nf, e(k,j)=abs(an-double(iidm_final(st, fns{j}(st.dd)))); end
    end
    err=[err; e]; %#ok<AGROW>
  end
  for j=1:nf
    fprintf('dmax_accel [%s]: max=%.5g p99.9=%.5g p99=%.5g mean=%.5g  (n=%d)\n', ...
            nm{j}, max(err(:,j)), prctile(err(:,j),99.9), prctile(err(:,j),99), mean(err(:,j)), size(err,1));
  end
end
