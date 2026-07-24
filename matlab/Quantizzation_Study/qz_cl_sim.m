function out = qz_cl_sim(traj, stepFun)
%QZ_CL_SIM  [Quantizzation_Study] Port FEDELE di utils/closed_loop_eval.simulate() (senza plant/channel).
%  Anello chiuso car-following: gap tracciato DIRETTAMENTE (nessun floor), collisione a s<=0, evento
%  cut_in a teletrasporto di gap. stepFun disaccoppia il controllore: oracolo o rete-a-nfrac, stesso anello.
%
%  traj    : struct con campi v_leader[1xN], s_init, v_init, gt_params[1x5], cut_in ([] | [k_1based new_gap]).
%  stepFun : @(x_phys, rst) -> [params(5), accel]. x_phys=[s;v;dv;vl] FISICO (non quantizzato: come simulate(),
%            cosi' il cancello di parita' oracolo-vs-Python e' pulito). rst=true al primo passo (reset stato).
%
%  Ritorna out.series (s,v,vl,dv,a per-step, PRE-update come simulate), out.params (Kx5), out.collided,
%  out.min_gap (s finale <=0 se collide, altrimenti min della serie -> come simulate riga 216), out.impact_dv.
  DT = 0.1;
  vl_all = traj.v_leader(:).'; N = numel(vl_all);
  cut = traj.cut_in;
  s = double(traj.s_init); v = double(traj.v_init);
  Ss = zeros(1,N); Sv = zeros(1,N); Svl = zeros(1,N); Sdv = zeros(1,N); Sa = zeros(1,N);
  P = zeros(N,5); collided = false; impact_dv = 0; last = N;
  for k = 1:N
    if ~isempty(cut) && k == cut(1)
      s = cut(2);                               % teletrasporto: nuovo leader piu' vicino (== simulate riga 172)
    end
    vl = vl_all(k);
    dv = v - vl;                                % dv = v - vl (corrente), come simulate/training
    [p, acc] = stepFun([s; v; dv; vl], k == 1);
    Ss(k)=s; Sv(k)=v; Svl(k)=vl; Sdv(k)=dv; Sa(k)=acc; P(k,:)=p(:).';
    v = max(0, v + acc*DT);                     % update balistico (gap NON clippato in basso)
    s = s + (vl - v)*DT;
    if s <= 0
      collided = true; impact_dv = max(0, v - vl); last = k; break;
    end
  end
  series = struct('s',Ss(1:last),'v',Sv(1:last),'vl',Svl(1:last),'dv',Sdv(1:last),'a',Sa(1:last));
  if collided, min_gap = s; else, min_gap = min(series.s); end
  out = struct('series',series,'params',P(1:last,:),'collided',collided, ...
               'min_gap',min_gap,'impact_dv',impact_dv,'N',last);
end
