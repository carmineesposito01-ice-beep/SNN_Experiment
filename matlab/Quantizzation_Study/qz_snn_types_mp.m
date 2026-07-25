function T = qz_snn_types_mp(dt, nf)
%QZ_SNN_TYPES_MP  [Quantizzation_Study] Copia PER-CAMPO di snn_types: nf = [nV nfat nacc naccw nraw nw]
%  (6 bit frazionari indipendenti). Interi fissi come in snn_types; accw mantiene il +4 (scorrimenti po2).
%  A nf=[13 13 13 13 13 13] i tipi coincidono con snn_types('fixed',13). NON tocca snn_types.m.
  assert(numel(nf) == 6, 'nf deve avere 6 elementi [V fatigue acc accw raw w]');
  switch dt
    case 'double'
      z = double([]);
      T = struct('V', z, 'fatigue', z, 'acc', z, 'accw', z, 'raw', z, 'w', z);
    case 'fixed'
      T = struct( ...
        'V',       fi([], true, 6 + nf(1), nf(1)), ...
        'fatigue', fi([], true, 4 + nf(2), nf(2)), ...
        'acc',     fi([], true, 6 + nf(3), nf(3)), ...
        'accw',    fi([], true, 13 + nf(4), nf(4) + 4), ...
        'raw',     fi([], true, 8 + nf(5), nf(5)), ...
        'w',       fi([], true, 3 + nf(6), nf(6)));
    otherwise
      error('qz_snn_types_mp:dt', 'dt deve essere ''double'' o ''fixed''');
  end
end
