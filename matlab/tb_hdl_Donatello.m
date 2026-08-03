function tb_hdl_Donatello()
%TB_HDL_DONATELLO  Testbench HDL (stream x_norm golden). GENERATO da make_hdl.
  d = load('champions_export.mat'); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  idx = find(arrayfun(@(c) strcmp(char(string(c.name)), 'Donatello'), champs), 1);
  c = champs(idx); Tf = snn_types('fixed', 13); N = size(c.x_norm, 1);
  for t = 1:N
    xn = cast(c.x_norm(t, :).', 'like', Tf.V);
    raw = snn_hdl_Donatello(xn); %#ok
  end
end
