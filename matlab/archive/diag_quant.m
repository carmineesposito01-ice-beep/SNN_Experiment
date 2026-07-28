function diag_quant()
%DIAG_QUANT  Distingue "quantizzazione di stato -> cascata di spike" (FONDAMENTALE)
%  da "bug del fixed harness". Core in DOUBLE ma con V/fatigue/V_LI (e input)
%  arrotondati a griglia 2^-f ad ogni tick: emula lo storage fixed SENZA gli altri
%  effetti fi (division/product/sum mode). Se riproduce il plateau ~3.5 del sweep fi
%  -> effetto fondamentale (spike cascade). Se resta accurato -> il fi ha un problema
%  di fimath/harness, non fondamentale (e allora e' fixabile).
  here = fileparts(mfilename('fullpath'));
  d = load(fullfile(here, 'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  fracs = [Inf 5 9 13];
  fprintf('%-13s |', 'champion');
  for f = fracs
    if isinf(f), fprintf('   f=inf'); else, fprintf('    f=%-2d', f); end
  end
  fprintf('   (max|d| param, stato quantizzato a 2^-f in double)\n');
  fprintf('%s\n', repmat('-', 1, 74));
  for i = 1:numel(champs)
    c = champs(i);
    fprintf('%-13s |', char(string(c.name)));
    for f = fracs
      fprintf(' %7.3f', run_quant(c, f));
    end
    fprintf('\n');
  end
end

function err = run_quant(c, f)
  W_IN = c.fc_weight; U = c.rec_U; Vr = c.rec_V; W_OUT = c.readout;
  DEL = c.delays; BTH = c.base_threshold(:); TJ = max(c.thresh_jump(:), 0);
  LD = c.leak_div(:); H = size(W_IN, 1); NT = 10; MAXD = 6;
  Vm = zeros(H, 1); fat = zeros(H, 1); sprev = zeros(H, 1); Vli = zeros(5, 1);
  xbuf = zeros(4, MAXD); N = size(c.x_phys, 1); P = zeros(N, 5);
  for t = 1:N
    xn = qgrid(snn_normalize(c.x_phys(t, :).', c.norm), f);
    for k = 1:NT
      xbuf(:, 2:end) = xbuf(:, 1:end-1); xbuf(:, 1) = xn;
      Iin = zeros(H, 1);
      for dd = 0:MAXD-1
        Iin = Iin + (W_IN .* (DEL == dd)) * xbuf(:, dd+1);
      end
      rec = U * (Vr * sprev);
      Vm  = qgrid(Vm - Vm ./ LD + Iin + rec, f);
      eth = BTH + max(fat, 0);
      s   = double(Vm >= eth);
      fat = qgrid(fat - fat ./ LD + s .* TJ, f);
      Vm  = qgrid(Vm - s .* eth, f);
      sprev = s;
      Vli = qgrid(Vli - Vli ./ 8 + W_OUT * s, f);
    end
    P(t, :) = snn_decode(Vli, c.param_lo, c.param_hi, c.decode_offset, c.logit_tau).';
  end
  err = max(max(abs(P - c.y_params)));
end

function y = qgrid(x, f)
  if isinf(f), y = x; else, y = round(x .* 2^f) ./ 2^f; end
end
