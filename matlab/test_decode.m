function test_decode()
%TEST_DECODE  [decode] parita' snn_decode_hdl (fixed, LUT) vs snn_decode (esatto) sul
%  raw FIXED del SNN Donatello. Isola l'errore del solo stadio decode.
  here = fileparts(mfilename('fullpath'));
  d = load(fullfile(here, 'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  idx = find(arrayfun(@(c) strcmp(char(string(c.name)), 'Donatello'), champs), 1);
  c = champs(idx);
  W = struct('hidden', c.hidden, 'rank', c.rank, 'n_ticks', c.n_ticks, 'max_delay', c.max_delay, ...
    'fc_weight', c.fc_weight, 'rec_U', c.rec_U, 'rec_V', c.rec_V, 'readout', c.readout, ...
    'delays', c.delays, 'base_threshold', c.base_threshold, 'thresh_jump', c.thresh_jump, ...
    'leak_div', c.leak_div);
  Tf = snn_types('fixed', 13);
  Traw = numerictype(1, 21, 13);
  snn_core([], [], Tf, 'reset');
  Nn = size(c.x_norm, 1);
  emax = 0; relmax = 0;
  rng = double(c.param_hi(:) - c.param_lo(:));
  for t = 1:Nn
    xn  = cast(c.x_norm(t, :).', 'like', Tf.V);
    raw = snn_core(xn, W, Tf);
    Pex  = snn_decode(double(raw), c.param_lo, c.param_hi, c.decode_offset, c.logit_tau);
    Phdl = double(snn_decode_hdl(fi(double(raw(:)), Traw)));
    e = abs(Pex(:) - Phdl(:));
    emax = max(emax, max(e));
    relmax = max(relmax, max(e ./ rng));
  end
  fprintf('decode HDL (LUT fixed) vs esatto: max abs err = %.5f  (max rel a range = %.4f%%)\n', emax, 100 * relmax);
  if emax < 0.05, disp('>> DECODE OK'); else, disp('>> rivedere'); end
end
