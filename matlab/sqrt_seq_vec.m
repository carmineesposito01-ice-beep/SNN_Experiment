function Y = sqrt_seq_vec(X) %#codegen
%SQRT_SEQ_VEC  Applica sqrt_seq a un vettore. Serve SOLO al cancello: mettere il loop DENTRO il MEX
%  rende sostenibile la prova ESAUSTIVA (262144 valori) senza ridurre il dominio.
  Y = zeros(numel(X), 1);
  for k = 1:numel(X)
    Y(k) = double(sqrt_seq(X(k)));
  end
end
