function code = dec_chart_code(srcDecode, decVariant, N, decInit)
%DEC_CHART_CODE  [SPLIT] La MF "DEC": riceve raw(5)+valid dalla SNN, fa latch + macchina a fasi del
%  decode -> i 5 parametri. E' la seconda meta' di chart_code, isolata: stessa logica [A1]+[A2].
%  raw e' sfix21_En13 (fi(true,21,13)), lo stesso tipo che rawl latchava nella chart unica.
%  decInit = 'shared' (default) | 'pvSplit' — [Leva2] come si inizializza.
%    'shared':  un unico `if isempty(pv)` per pv + tutti i persistent del decode.
%    'pvSplit': `pv` ha il SUO flag isempty, il resto resta raggruppato. Motivo: il path critico di
%               sp_fast (92,9 MHz, 4 liv) NON e' aritmetica profonda ma il flag di init `pv_not_empty`
%               che entra nel datapath (startpoint pv_not_empty_reg_rep). Isolarlo abbassa il fanout
%               del flag su pv. ⚠️ Si separa SOLO pv: separare anche gli init delle fasi rende VIVA la
%               catena rawl->decode_a->... (provato sul blocco chart: perVar-v1 = 29,7 MHz, PEGGIO).
  if nargin < 4 || isempty(decInit), decInit = 'shared'; end
  [pers, dec, ~, ini] = decode_phase_code(decVariant, N);   % riusa la macchina a fasi di chart_code
  if strcmp(decInit, 'pvSplit')
    initBlock = [{'  if isempty(pv)'
                  '    pv = fi(zeros(5,1), 1, 21, 13);'
                  '  end'
                  '  if isempty(started_dec)'}
                 ini(:)
                 {'    started_dec = true;'
                  '  end'}];
    persDecl = ['  persistent pv started_dec ' pers];
  else
    initBlock = [{'  if isempty(pv)'
                  '    pv = fi(zeros(5,1), 1, 21, 13);'}
                 ini(:)
                 {'  end'}];
    persDecl = ['  persistent pv ' pers];
  end
  Lmain = [{
    'function [v0, T, s0, a, b] = DEC(raw, valid)'
    '%#codegen'
    '% [SPLIT] Solo il decode: latch di raw + fasi. Riceve raw(5)+valid dalla MF SNN (entita'' a se'').'
    persDecl}
    initBlock
    dec(:)
    {'  v0 = pv(1); T = pv(2); s0 = pv(3); a = pv(4); b = pv(5);'
    'end'}];
  L = [Lmain(:); {''}; inlined_header()];
  code = strjoin(L, newline);
  code = [code newline newline srcDecode];
end


