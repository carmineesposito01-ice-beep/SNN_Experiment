function n = t7_plant_par(workdir, O, idx)
%T7_PLANT_PAR  Cancello PLANT-PAR sull'intero perimetro: il plant del testbench riproduce qz_cl_sim
%  bit-per-bit, su ogni scenario, pilotato con la sequenza accel del riferimento e SENZA DUT.
%  Isola i difetti d'integrazione PRIMA dell'anello live: senza, un difetto del plant si travestirebbe
%  da difetto del blocco.
%
%  Verilog `real` e' IEEE-754 double come MATLAB: la parita' dev'essere ESATTA, non "al livello del
%  float". Un dmax di ~1e-12 non e' tolleranza numerica accettabile: e' il sintomo di un difetto
%  (in T7a era il lettore esadecimale — vedi t7_hexread).
%
%  workdir : dir con plant_<i>.txt prodotti da tb_plant_only.v
%  O       : cell degli output qz_cl_sim dell'ORACOLO (stessa sequenza accel data al TB)
%  idx     : indici degli scenari (solo per i messaggi)
%  n       : disallineamenti totali (0 = passato)
  n = 0;
  for i = 1:numel(idx)
    o = O{i};
    p = fullfile(workdir, sprintf('plant_%d.txt', i));
    assert(isfile(p), 'PLANT-PAR: manca %s', p);
    T = readlines(p); T = T(strlength(T) > 0);
    body = T(~startsWith(T,"END"));
    tail = T(startsWith(T,"END"));
    assert(numel(tail) == 1, '%s: attesa UNA riga END, trovate %d', p, numel(tail));
    m = numel(body);
    S = zeros(m,1); V = zeros(m,1); VL = zeros(m,1); DV = zeros(m,1);
    for r = 1:m
      f = split(strtrim(body(r)));
      assert(numel(f) == 5, '%s riga %d: attesi 5 campi, trovati %d', p, r, numel(f));
      S(r)  = t7_hexread(f(2)); V(r)  = t7_hexread(f(3));
      VL(r) = t7_hexread(f(4)); DV(r) = t7_hexread(f(5));
    end
    k = min(m, o.N);
    d = sum([S(1:k) ~= o.series.s(1:k).'; V(1:k)  ~= o.series.v(1:k).'; ...
             VL(1:k) ~= o.series.vl(1:k).'; DV(1:k) ~= o.series.dv(1:k).']);
    if m ~= o.N
      d = d + 1;    % anche la lunghezza (troncamento su collisione) deve coincidere
      fprintf('  PLANT-PAR scenario %d: lunghezza TB=%d vs MATLAB=%d\n', idx(i), m, o.N);
    end
    if d > 0
      k1 = find(S(1:k) ~= o.series.s(1:k).', 1);
      if ~isempty(k1)
        fprintf('  PLANT-PAR scenario %d: primo scarto su s al passo %d (TB=%.17g ML=%.17g)\n', ...
                idx(i), k1, S(k1), o.series.s(k1));
      end
    end
    n = n + d;
  end
  fprintf('PLANT-PAR    : %d disallineamenti su %d scenari\n', n, numel(idx));
end
