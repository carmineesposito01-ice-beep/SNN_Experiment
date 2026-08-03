function run_hdl_verify()
%RUN_HDL_VERIFY  Conferma che i wrapper snn_hdl_<name> (pesi baked + snn_core fixed)
%  riproducono il golden come il sweep f=13. Alimenta x_norm (fi Q5.13) -> raw ->
%  decode double -> confronto con y_params. Deve dare ~0 (== sweep Q?.13).
  here = fileparts(mfilename('fullpath'));
  d = load(fullfile(here, 'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  Tf = snn_types('fixed', 13);
  for i = 1:numel(champs)
    c = champs(i); name = char(string(c.name)); N = size(c.x_norm, 1);
    f = str2func(['snn_hdl_' name]);
    snn_core([], [], Tf, 'reset');                     % reset stato fixed
    P = zeros(N, 5);
    for t = 1:N
      xn = cast(c.x_norm(t, :).', 'like', Tf.V);       % fi Q5.13
      raw = f(xn);
      P(t, :) = snn_decode(double(raw), c.param_lo, c.param_hi, ...
                           c.decode_offset, c.logit_tau).';
    end
    fprintf('%-13s  wrapper|d|=%.4f  (atteso ~ sweep f=13)\n', ...
            name, max(max(abs(P - c.y_params))));
  end
  disp('HDL wrapper verify done');
end
