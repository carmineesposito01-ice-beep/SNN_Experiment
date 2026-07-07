function T = snn_types(dt)
%SNN_TYPES Prototipi di tipo per il core type-parametrizzato.
%  dt = 'double' (parita' vs golden) | 'fixed' (HDL, Qm.n da FPGA_REPORT).
  switch dt
    case 'double'
      z = double([]);
      T = struct('V', z, 'fatigue', z, 'acc', z, 'raw', z, 'w', z);
    case 'fixed'
      T = struct( ...
        'V',       fi([], true, 11, 5), ...   % Q5.5
        'fatigue', fi([], true,  9, 5), ...   % Q3.5
        'acc',     fi([], true,  9, 5), ...   % accumulatori Q3.5
        'raw',     fi([], true, 13, 5), ...   % readout LI Q7.5
        'w',       fi([], true,  8, 5));      % pesi po2 (placeholder Plan-2 HDL)
    otherwise
      error('snn_types:dt', 'dt deve essere ''double'' o ''fixed''');
  end
end
