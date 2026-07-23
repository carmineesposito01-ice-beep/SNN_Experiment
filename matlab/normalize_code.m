function L = normalize_code(nrm)
%NORMALIZE_CODE  Righe della funzione locale `local_normalize` (fisico -> xn fixed).
%  UNICA fonte, condivisa da chart_code (blocchi HDL-ready) e da acciidm_chart_code (SP2):
%  duplicarla farebbe divergere i blocchi in silenzio alla prima modifica dei reciproci.
  M = @(x) sprintf('%.17g', x);
  % SPLIT in ops (clamp -> operandi) + mul (operandi -> xn): local_normalize resta la COMPOSIZIONE,
  % bit-identica per i chiamanti condivisi (chart_code, acciidm). Lo split serve a splitpipe per
  % registrare gli OPERANDI fra clamp e moltiplicazione (rompe il percorso ingresso->normalize->go).
  L = {
    'function xn = local_normalize(s, v, dv, v_l, T)'
    '%LOCAL_NORMALIZE  fisico -> xn (fixed) = composizione ops+mul (bit-identica all''originale).'
    '%  Nel deployato la normalize gira in SW float e all''HDL arriva gia'' xn (HDL_PHASE §3.1).'
    '  op = local_normalize_ops(s, v, dv, v_l);'
    '  xn = local_normalize_mul(op, T);'
    'end'
    ''
    'function op = local_normalize_ops(s, v, dv, v_l)'
    '%LOCAL_NORMALIZE_OPS  clamp del dv -> operandi [s; v; d_clamped; v_l] (pre-moltiplicazione).'
    ['  DVc = fi(' M(nrm(3)) ', 1, 24, 13);   % 24-13-1 = 10 bit interi: DV=' M(nrm(3)) ' ci sta']
    '                                   % (con Q5.13/18bit saturerebbe a ~16 -> clamp sbagliato)'
    '  d = dv;                          % clamp a +-DV. NB: d(:) = ... per NON cambiare il tipo di d'
    '  if d >  DVc, d(:) =  DVc; end    %     (codegen: una variabile non puo'' cambiare tipo, HDL_PHASE §9)'
    '  if d < -DVc, d(:) = -DVc; end'
    '  op = [s; v; d; v_l];'
    'end'
    ''
    'function xn = local_normalize_mul(op, T)'
    '%LOCAL_NORMALIZE_MUL  operandi -> xn. RECIPROCI a Q?.30 (NON Q?.20): con Q?.20 xn devia di 1 LSB'
    '%  ~1 volta su 25 step -> uno spike flippa -> params divergono. Con Q?.30 e ingressi >=20 bit'
    '%  frazionari, xn e'' IDENTICO al riferimento float (0 diff).'
    ['  invS   = fi(' M(1/nrm(1))      ', 1, 34, 30);']
    ['  invV   = fi(' M(1/nrm(2))      ', 1, 34, 30);']
    ['  inv2DV = fi(' M(1/(2*nrm(3)))  ', 1, 34, 30);']
    ['  invVL  = fi(' M(1/nrm(4))      ', 1, 34, 30);']
    ['  DVc    = fi(' M(nrm(3)) ', 1, 24, 13);']
    '  xn = cast(zeros(4,1), ''like'', T.V);'
    '  xn(1) = cast(op(1) * invS, ''like'', T.V);'
    '  xn(2) = cast(op(2) * invV, ''like'', T.V);'
    '  xn(3) = cast((op(3) + DVc) * inv2DV, ''like'', T.V);'
    '  xn(4) = cast(op(4) * invVL, ''like'', T.V);'
    'end'
  };
  L = L(:);
end


