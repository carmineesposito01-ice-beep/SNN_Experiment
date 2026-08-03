function check_hdl()
%CHECK_HDL  Gate HDL-readiness (v1): coder.screener sul datapath del core.
%  snn_core (shift-add) + snn_normalize (affine) devono avere 0 messaggi e 0 chiamate
%  non supportate. Il DECODE (sigmoid/exp) e' ESCLUSO di proposito: stadio isolato ->
%  LUT/CORDIC/PS nel build HDL (spec §3.2/§7). checkhdl sul blocco intero fallirebbe
%  sull'exp del decode: e' atteso, non un difetto del core.
  targets = {'snn_core', 'snn_normalize'};
  total = 0;
  for i = 1:numel(targets)
    fn = targets{i};
    info = coder.screener(fn);
    nm = numel(info.Messages); nu = numel(info.UnsupportedCalls);
    fprintf('coder.screener(%-14s): %d messaggi, %d chiamate non supportate\n', fn, nm, nu);
    for j = 1:nm, try, fprintf('   MSG:   %s\n', char(info.Messages(j).Text)); catch, end, end
    for j = 1:nu, try, fprintf('   UNSUP: %s\n', char(info.UnsupportedCalls(j).Name)); catch, end, end
    total = total + nm + nu;
  end
  if total == 0
    disp('HDL READINESS (core): OK');
  else
    error('check_hdl:FAIL', 'coder.screener: %d issue totali sul core', total);
  end
end
