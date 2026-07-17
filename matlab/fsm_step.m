function accel = fsm_step(s, v, dv, v_l, p, rst) %#codegen
%FSM_STEP  [SP4-M-FSM G2] Wrapper MEX-abile di acc_iidm_fsm con T=acc_types('fixed') COSTRUITO DENTRO
%  (coder.const), gemello di collect_step per acc_iidm_open. Serve a far girare G2 sul dataset intero in
%  minuti invece che in ore: acc_iidm_fsm in fi INTERPRETATO costa ~47 min su 60 traj (il muro di
%  Donatello: "core fi interpretato = ore -> obbligo MEX").
  accel = acc_iidm_fsm(s, v, dv, v_l, p, rst);   % fixed-only: le fasi costruiscono acc_types dentro
end
