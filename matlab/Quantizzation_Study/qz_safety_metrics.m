function m = qz_safety_metrics(series, collided, min_gap, impact_dv)
%QZ_SAFETY_METRICS  [Quantizzation_Study] SSM di sicurezza — port di closed_loop_eval.safety_metrics():
%  collision, min_gap, min_TTC, max_DRAC, brake_margin_min (margine di evitabilita' con SEGNO: <0 = la
%  collisione era fisicamente inevitabile), frac_drac_critical, impact_dv. Costanti come nel motore canonico.
  B_MAX = 9.0; DRAC_STAR = 3.35;
  s = series.s; dv = series.dv;
  closing = dv > 1e-3;
  ttc = inf(size(s)); ttc(closing) = s(closing) ./ max(dv(closing), 1e-6);
  drac = zeros(size(s)); drac(closing) = dv(closing).^2 ./ (2 * max(s(closing), 1e-3));
  brake_margin = s - max(0, dv).^2 / (2 * B_MAX);
  fin = isfinite(ttc);
  m = struct();
  m.collided           = logical(collided);
  m.min_gap            = min_gap;
  m.impact_dv          = impact_dv;
  if any(fin), m.min_ttc = min(ttc(fin)); else, m.min_ttc = inf; end
  m.max_DRAC           = max([drac, 0]);
  m.brake_margin_min   = min(brake_margin);
  m.frac_drac_critical = mean(drac > DRAC_STAR);
end
