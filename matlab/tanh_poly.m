function th = tanh_poly(dd) %#codegen
% [B2.0-2b A2b] tanh via polinomio grado 9 (Horner in fixed) su [-4,4] con clamp, in u=dd/4 NORMALIZZATO
%  (i coeff diventano O(1), rappresentabili in En17; senza, il coeff di grado alto ~1e-6 cade sotto 1 LSB
%  e il poly si rompe). Coeff = polyfit(tanh(4u), u in [-1,1], 9) -- odd poly (coeff pari ~0), EMBEDDATI
%  (niente polyfit a runtime -> veloce interpretato + HDL-safe). Approssimato (NON bit-exact).
  x = dd;
  if x <  -4, x(:) = fi(-4, 1, 19, 8);        end
  if x >=  4, x(:) = fi(4 - 1/256, 1, 19, 8); end
  u = fi(x * 0.25, 1, 19, 17);                       % u = x/4 in [-1,1]
  c = [9.25207153871, 0, -24.6120071631, 0, 24.5905264828, 0, -11.908414092, 0, 3.71013330643, 0];
  Tacc = numerictype(1, 32, 17);
  acc = fi(c(1), Tacc);
  for i = 2:10
    acc = fi(acc*u + c(i), Tacc);
  end
  th = fi(acc, 1, 19, 17);
end
