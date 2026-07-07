function xn = snn_normalize(x_phys, norm)
%SNN_NORMALIZE  x_phys [4x1] fisico -> xn [4x1] normalizzato. norm=[S V DV VL].
%  Identico a data/generator.py (config.py:110-113).
  S = norm(1); V = norm(2); DV = norm(3); VL = norm(4);
  dv = min(max(x_phys(3), -DV), DV);
  xn = [ x_phys(1)/S; x_phys(2)/V; (dv + DV)/(2*DV); x_phys(4)/VL ];
end
