function f = t7_step_block()
%T7_STEP_BLOCK  stepFun per qz_cl_sim: il BLOCCO composto, via il golden MEX bit-identico.
%
%  acciidm_m_traj_mex e' PROVATO == blocco (probe P4/G2 e test_t7_step_block: dmax=0) e utilizzabile
%  UN control-step alla volta: lo stato ricorrente (SNN + filtro OU) vive dentro acciidm_m_algo e
%  sopravvive fra chiamate MEX. Verificato in P4/G1 con sensibilita' dimostrata (azzerando lo stato a
%  meta' sequenza il risultato cambia di 0,289).
%
%  QUANTIZZAZIONE — FLOOR. L'ingresso viene portato a fixdt(1,32,20) con arrotondamento Floor perche':
%    * la Data Type Conversion di Simulink (che alimenta il blocco) usa Floor di default;
%    * il testbench Verilog usa $floor, che coincide esattamente con fi(...,'Floor') (probe P4b/R1b);
%    * acciidm_m_traj applica internamente fi(...) con arrotondamento NEAREST: su valori GIA'
%      Floor-quantizzati quel fi e' un no-op (P4b/R2).
%  Senza questa convenzione i tre percorsi divergono: Nearest e Floor differiscono sul 49,8 % dei
%  valori (P4b/R1), e in anello chiuso il plant integra, quindi la divergenza si accumula.
%
%  I 5 PARAMETRI non escono dal golden: acciidm_m_traj restituisce solo accel (e' l'estrazione
%  verbatim del blocco monolitico). qz_cl_sim non li usa per la dinamica, li registra soltanto ->
%  qui si restituisce NaN, non zero: un uso improprio a valle esplode invece di passare per un
%  numero plausibile. I parametri per le metriche vengono dall'RTL (spec §5).
%
%  ⚠️ CONSEGUENZA del segnaposto NaN: `isequal` su due strutture golden restituisce SEMPRE false,
%     perche' isequal(NaN,NaN) e' false. Per confrontare golden usare **isequaln**. Non e' un difetto
%     della cache: verificato campo per campo (series/collided/min_gap/impact_dv/N tutti uguali).
  HOLD_G = 500;                                     % >= latenza dell'algoritmo monolitico (~358), come T5
  FM = fimath('RoundingMethod','Floor','OverflowAction','Saturate');
  assert(~isempty(which('acciidm_m_traj_mex')), ...
         'MEX acciidm_m_traj_mex assente: eseguire build_acciidm_m_golden()');
  f = @step;

  function [p, acc] = step(x, rst)
    if rst, clear acciidm_m_traj_mex; end            % nuovo scenario -> stato azzerato
    xq  = double(fi(x(:), 1, 32, 20, FM));
    acc = double(acciidm_m_traj_mex(xq, HOLD_G));
    p   = nan(5,1);
  end
end
