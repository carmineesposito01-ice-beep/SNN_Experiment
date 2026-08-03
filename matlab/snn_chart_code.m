function code = snn_chart_code(srcRom, srcTypes, srcFsm, nrm, pipe)
%SNN_CHART_CODE  [SPLIT] La MF "SNN": normalize + snn_b2_fsm, uscita raw(5) + valid. NIENTE decode.
%  Stessa logica di edge-trigger e stessi persistent di controllo di chart_code, ma si FERMA a raw.
%  pipe=true [SPLITPIPE]: REGISTRO su xn -> rompe il percorso combinatorio ingresso->normalize->go
%  (il muro reale io-timed). Fuori dal core snn_b2_fsm congelato. +1 clock di latenza, bit-exact.
  if nargin < 5 || isempty(pipe), pipe = false; end
  if pipe
    Lmain = {
      'function [raw, valid] = SNN(s, v, dv, v_l)'
      '%#codegen'
      '% [SPLITPIPE] REGISTRO sugli OPERANDI del normalize (fra clamp e moltiplicazione): la'
      '% moltiplicazione a 34 bit finisce in uno stadio suo -> rompe ingresso->normalize->go. La'
      '% moltiplicazione e'' a valle di op_reg; l''edge-trigger confronta gli OPERANDI registrati (equivale'
      '% a confrontare xn, dato che mul e'' deterministica). +1 clock di latenza. Fuori dal core.'
      '  Tt = snn_types(''fixed'', 13);'
      '  op = local_normalize_ops(s, v, dv, v_l);'
      '  persistent op_reg op_prev started prime'
      '  if isempty(started)'
      '    op_reg = cast(zeros(4,1), ''like'', op);  % init COSTANTE (non =op: eviterebbe il registro'
      '    op_prev = op_reg;                        %  con un bypass combinatorio ingresso->mul->xbuf)'
      '    started = true; prime = true;'
      '    go = false;'
      '  elseif prime'
      '    prime = false;'
      '    go = true;'
      '  else'
      '    go = any(op_reg ~= op_prev);'
      '  end'
      '  op_prev = op_reg;'
      '  xn = local_normalize_mul(op_reg, Tt);'
      '  [raw, valid] = snn_b2_fsm(xn, go);'
      '  op_reg = op;'
      'end'};
  else
  Lmain = {
    'function [raw, valid] = SNN(s, v, dv, v_l)'
    '%#codegen'
    '% [SPLIT] Solo il forward SNN: normalize + snn_b2_fsm. Il decode e'' un''ENTITA'' a se'' (MF DEC).'
    '  Tt = snn_types(''fixed'', 13);'
    '  xn = local_normalize(s, v, dv, v_l, Tt);'
    '  persistent xprev started'
    '  if isempty(started)'
    '    xprev = xn; started = true;'
    '    go = true;'
    '  else'
    '    go = any(xn ~= xprev);'
    '  end'
    '  xprev = xn;'
    '  [raw, valid] = snn_b2_fsm(xn, go);'
    'end'};
  end
  L = [Lmain(:); {''}; normalize_code(nrm); {''}; inlined_header()];
  code = strjoin(L, newline);
  code = [code newline newline srcRom newline newline srcTypes newline newline srcFsm];
end


