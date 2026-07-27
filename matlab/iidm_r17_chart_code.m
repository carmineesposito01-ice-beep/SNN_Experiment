function code = iidm_r17_chart_code()
%IIDM_R17_CHART_CODE  Chart del blocco ACC-IIDM standalone = la chart M R17 (acciidm_m_chart_code) MENO la
%  SNN. Mantiene VERBATIM le fasi IIDM ottimizzate R17 (divisore+radice digit-recurrence, USE 4 fasi,
%  FINAL/PREP/OU a stadi); i 5 parametri IDM arrivano dai 9 ingressi invece che da snn_b2_fsm+decode.
%  nfrac=8 (l'architettura R17 e' nfrac=8-specifica): usa acc_types('fixed') di default, niente manopola.
%  Le funzioni-fase sono INLINATE dai sorgenti VERI (single source con acc_iidm_fsm/il model): la chart
%  NON ricalcola la matematica. Rispetto a acciidm_m_chart_code: rimossi srcRom/srcTypes/srcFsm/srcLut
%  (SNN+decode+normalize) e le fasi 1/20/12/23/18 (decode); pv arriva dagli ingressi.
  here = fileparts(mfilename('fullpath'));
  rd = @(f) fileread(fullfile(here, f));
  srcAccT  = rd('acc_types.m');
  srcFDiv  = rd('fsm_div.m');
  srcPrep  = [rd('iidm_prep.m')   newline newline rd('iidm_prep_a.m') newline newline ...
              rd('iidm_prep_a2.m') newline newline rd('iidm_prep_b.m')];
  srcNd    = rd('iidm_nd.m');
  srcUse   = [rd('iidm_use.m')   newline newline rd('iidm_use_a.m') newline newline ...
              rd('iidm_use_m.m') newline newline rd('iidm_use_m2.m') newline newline rd('iidm_use_b.m')];
  srcTanh  = rd('iidm_tanh.m');
  srcTanhLut = rd('tanh_lut_full.m');
  srcFinal = [rd('iidm_final.m')   newline newline rd('iidm_final_a.m') newline newline ...
              rd('iidm_final_b.m') newline newline rd('iidm_final_c.m')];
  srcDivNb = rd('div_seq_nb.m');  srcDivSu = rd('div_seq_setup.m');
  srcDivSt = rd('div_seq_step.m'); srcDivFi = rd('div_seq_fin.m');
  srcSqNb  = rd('sqrt_seq_nb.m');  srcSqSu  = rd('sqrt_seq_setup.m');
  srcSqSt  = rd('sqrt_seq_step.m'); srcSqFi  = rd('sqrt_seq_fin.m');
  srcAb    = rd('iidm_ab.m'); srcSabx = rd('iidm_sabx.m'); srcSabxM = rd('iidm_sabx_mul.m');

  Lmain = {
    'function accel = ACC_IIDM(s, v, dv, v_l, v0, T, s0, a, b)'
    '%#codegen'
    '% Blocco ACC-IIDM standalone R17: la chart M (Donatello_ACC_IIDM_M) MENO la SNN. I 5 parametri IDM'
    '%  arrivano IN INGRESSO (niente snn_b2_fsm/decode/normalize). Mantiene TUTTE le ottimizzazioni R17.'
    '%  Edge-triggered: 1 cambio d''ingresso = 1 inferenza; l''accel tiene fino alla successiva. nfrac=8.'
    '  Ta = acc_types(''fixed'');'
    '  p  = [v0; T; s0; a; b];'
    '  x  = [s; v; dv; v_l; v0; T; s0; a; b];'
    '  persistent pv xprev started acc phase kdiv st alf vlp numl denl ql thl dA dR dQ dB dsq dkbit dns sX sR sQ sk sabv blv ouv acbl qaf qbf'
    '  if isempty(started)'
    '    pv = cast(p, ''like'', fi(zeros(5,1), 1, 21, 13));'
    '    xprev = x; started = true;'
    '    acc = cast(0, ''like'', Ta.out);'
    '    phase = uint8(0); kdiv = uint8(1);'
    '    alf = cast(0, ''like'', Ta.acc); vlp = cast(v_l, ''like'', Ta.st);'
    '    [ouv, alf, vlp] = iidm_prep_a(v_l, true, alf, vlp);'
    '    sX = fi(0, 0, sqrt_seq_nb()*2, 0); sR = fi(0, 0, sqrt_seq_nb()+2, 0);'
    '    sQ = fi(0, 0, sqrt_seq_nb(), 0);   sk = uint8(0);'
    '    sabv = sqrt_seq_fin(sQ);'
    '    [qaf, qbf] = iidm_ab(pv(:));'
    '    [st, alf, vlp] = iidm_prep(s, v, dv, v_l, pv(:), true, alf, vlp, sabv);'
    '    numl = cast(0, ''like'', Ta.acc); denl = cast(1, ''like'', Ta.acc); ql = cast(0, ''like'', Ta.acc);'
    '    dA = fi(0, 0, div_seq_nb(), 0); dQ = fi(0, 0, div_seq_nb(), 0);'
    '    dR = fi(0, 0, 20, 0); dB = fi(0, 0, 20, 0);'
    '    dsq = false; dkbit = uint8(0); dns = int8(0);'
    '    thl = tanh(cast(0, ''like'', Ta.acc));'
    '    blv = iidm_final_a(st, thl);'
    '    acbl = iidm_final_b(st, blv);'
    '    go = true;'
    '  else'
    '    go = any(x ~= xprev);'
    '  end'
    '  xprev = x;'
    '  if go                                % nuova inferenza: params dagli ingressi, avvia a SQRT-INIT'
    '    pv = cast(p, ''like'', pv);'
    '    phase = uint8(10);'
    '  end'
    '  if phase == 10                       % SQRT-INIT'
    '    [qaf, qbf] = iidm_ab(pv(:));'
    '    phase = uint8(21);'
    '  elseif phase == 21                   % SQRT-PRE'
    '    sX = sqrt_seq_setup(iidm_sabx_mul(qaf, qbf));'
    '    sR(:) = 0; sQ(:) = 0; sk = uint8(sqrt_seq_nb());'
    '    phase = uint8(11);'
    '  elseif phase == 11                   % SQRT-STEP'
    '    [sX, sR, sQ] = sqrt_seq_step(sX, sR, sQ);'
    '    sk = sk - uint8(1);'
    '    if sk == uint8(0)'
    '      sabv = sqrt_seq_fin(sQ);'
    '      phase = uint8(2);'
    '    end'
    '  elseif phase == 2                    % PREP (filtro OU, la sqrt arriva fatta)'
    '    [ouv, alf, vlp] = iidm_prep_a(v_l, false, alf, vlp);'
    '    phase = uint8(17);'
    '  elseif phase == 17                   % OU-B'
    '    alf = iidm_prep_a2(ouv, alf);'
    '    phase = uint8(16);'
    '  elseif phase == 16                   % PREP-B'
    '    st = iidm_prep_b(s, v, dv, v_l, pv(:), alf, sabv);'
    '    kdiv = uint8(1); phase = uint8(3);'
    '  elseif phase == 3                    % ND'
    '    [numl, denl] = iidm_nd(kdiv, st);'
    '    phase = uint8(4);'
    '  elseif phase == 4                    % DIV-INIT'
    '    [dA, dB, dsq] = div_seq_setup(numl, denl);'
    '    dR(:) = 0; dQ(:) = 0; dkbit = uint8(div_seq_nb());'
    '    dns = int8(0);'
    '    if numl > 0'
    '      dns = int8(1);'
    '    elseif numl < 0'
    '      dns = int8(-1);'
    '    end'
    '    phase = uint8(8);'
    '  elseif phase == 8                    % DIV-STEP'
    '    [dA, dR, dQ] = div_seq_step(dA, dR, dQ, dB);'
    '    dkbit = dkbit - uint8(1);'
    '    if dkbit == uint8(0)'
    '      phase = uint8(9);'
    '    end'
    '  elseif phase == 9                    % DIV-FIN'
    '    ql(:) = div_seq_fin(dQ, dsq, dB == 0, dns);'
    '    phase = uint8(5);'
    '  elseif phase == 5                    % USE-A'
    '    st = iidm_use_a(kdiv, ql, st);'
    '    phase = uint8(15);'
    '  elseif phase == 15                   % USE-M'
    '    st = iidm_use_m(kdiv, st);'
    '    phase = uint8(22);'
    '  elseif phase == 22                   % USE-M2'
    '    st = iidm_use_m2(kdiv, st);'
    '    phase = uint8(13);'
    '  elseif phase == 13                   % USE-B (loop k=1..5)'
    '    st = iidm_use_b(kdiv, ql, st);'
    '    if kdiv >= 5'
    '      phase = uint8(6);'
    '    else'
    '      kdiv = kdiv + 1; phase = uint8(3);'
    '    end'
    '  elseif phase == 6                    % TANH'
    '    thl(:) = iidm_tanh(st);'
    '    phase = uint8(7);'
    '  elseif phase == 7                    % FINAL-A'
    '    blv = iidm_final_a(st, thl);'
    '    phase = uint8(14);'
    '  elseif phase == 14                   % FINAL-B'
    '    acbl = iidm_final_b(st, blv);'
    '    phase = uint8(19);'
    '  elseif phase == 19                   % FINAL-C -> accel'
    '    acc = iidm_final_c(st, acbl);'
    '    phase = uint8(0);'
    '  end'
    '  accel = acc;'
    'end'
  };
  code = strjoin(Lmain(:), newline);
  code = [code newline newline srcAccT newline newline srcFDiv ...
          newline newline srcPrep newline newline srcNd newline newline srcUse ...
          newline newline srcTanh newline newline srcTanhLut newline newline srcFinal ...
          newline newline srcDivNb newline newline srcDivSu ...
          newline newline srcDivSt newline newline srcDivFi ...
          newline newline srcSqNb newline newline srcSqSu ...
          newline newline srcSqSt newline newline srcSqFi ...
          newline newline srcAb   newline newline srcSabx ...
          newline newline srcSabxM];
end
