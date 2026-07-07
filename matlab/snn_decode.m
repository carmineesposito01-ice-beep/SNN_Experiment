function p = snn_decode(raw, param_lo, param_hi, decode_offset, logit_tau)
%SNN_DECODE  raw [5x1] (potenziale LI) -> p [5x1] parametri fisici IDM.
%  p = lo + (hi-lo).*sigmoid((raw-offset)./tau)  (network.py:437-438)
  adj = (raw(:) - decode_offset(:)) ./ logit_tau(:);
  s   = 1 ./ (1 + exp(-adj));
  p   = param_lo(:) + (param_hi(:) - param_lo(:)) .* s;
end
