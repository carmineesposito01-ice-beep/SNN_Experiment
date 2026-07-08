function diag_ranges()
%DIAG_RANGES  Picchi di ampiezza dei segnali interni (calcolati in DOUBLE) per
%  dimensionare i bit INTERI dei tipi fixed. Rivela quale tra V (Q5.f, +-32),
%  fatigue (Q3.f, +-8), V_LI (Q7.f, +-128) satura -> spiega il plateau del sweep.
  here = fileparts(mfilename('fullpath'));
  d = load(fullfile(here, 'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  fprintf('%-13s | %7s %7s %7s %7s %7s   (caps: V32 fat8 -- LI128)\n', ...
          'champion', '|V|', '|fatig|', '|Iin|', '|drive|', '|V_LI|');
  fprintf('%s\n', repmat('-', 1, 78));
  for i = 1:numel(champs)
    c = champs(i);
    W_IN = c.fc_weight; U = c.rec_U; Vr = c.rec_V; W_OUT = c.readout;
    DEL = c.delays; BTH = c.base_threshold(:); TJ = max(c.thresh_jump(:), 0);
    LD = c.leak_div(:); H = size(W_IN, 1); NT = 10; MAXD = 6;
    Vm = zeros(H, 1); fat = zeros(H, 1); sprev = zeros(H, 1); Vli = zeros(5, 1);
    xbuf = zeros(4, MAXD); N = size(c.x_phys, 1);
    mV = 0; mF = 0; mI = 0; mD = 0; mL = 0;
    for t = 1:N
      xn = snn_normalize(c.x_phys(t, :).', c.norm);
      for k = 1:NT
        xbuf(:, 2:end) = xbuf(:, 1:end-1); xbuf(:, 1) = xn;
        Iin = zeros(H, 1);
        for dd = 0:MAXD-1
          Iin = Iin + (W_IN .* (DEL == dd)) * xbuf(:, dd+1);
        end
        rec = U * (Vr * sprev);
        drive = Iin + rec;
        Vm = Vm - Vm ./ LD + drive;
        eth = BTH + max(fat, 0);
        s = double(Vm >= eth);
        fat = fat - fat ./ LD + s .* TJ;
        Vm = Vm - s .* eth;
        sprev = s;
        Vli = Vli - Vli ./ 8 + W_OUT * s;
        mV = max(mV, max(abs(Vm)));   mF = max(mF, max(abs(fat)));
        mI = max(mI, max(abs(Iin)));  mD = max(mD, max(abs(drive)));
        mL = max(mL, max(abs(Vli)));
      end
    end
    fprintf('%-13s | %7.2f %7.2f %7.2f %7.2f %7.2f\n', ...
            char(string(c.name)), mV, mF, mI, mD, mL);
  end
end
