function T = snn_types(dt, nfrac)
%SNN_TYPES Prototipi di tipo per il core type-parametrizzato.
%  dt = 'double' (parita' vs golden) | 'fixed' (HDL, Qm.n).
%  nfrac (opz., default 5) = bit frazionari del path fixed; i bit INTERI restano
%  fissi (range invariato), varia solo la risoluzione -> per tarare i word-length
%  col ginocchio errore/risorse (run_fixed_sweep). nfrac=5 == config storica.
  if nargin < 2, nfrac = 5; end
  switch dt
    case 'double'
      z = double([]);
      T = struct('V', z, 'fatigue', z, 'acc', z, 'accw', z, 'raw', z, 'w', z);
    case 'fixed'
      f = nfrac;
      T = struct( ...
        'V',       fi([], true, 6 + f, f), ...    % Q5.f  (int 5)
        'fatigue', fi([], true, 4 + f, f), ...    % Q3.f  (int 3)
        'acc',     fi([], true, 6 + f, f), ...    % accumulatore I_input Q5.f (int 5: un tap di delay arriva a ~8)
        'accw',    fi([], true, 13 + f, f + 4), ...% accumulatore LARGO Q8.(f+4): +4 frac per shift po2 esatti
        'raw',     fi([], true, 8 + f, f), ...    % readout LI Q7.f (int 7)
        'w',       fi([], true, 3 + f, f));       % pesi po2 Q2.f (esatti per f>=5)
    otherwise
      error('snn_types:dt', 'dt deve essere ''double'' o ''fixed''');
  end
end
