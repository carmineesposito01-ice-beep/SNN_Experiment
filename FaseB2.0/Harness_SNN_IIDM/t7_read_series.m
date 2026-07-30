function R = t7_read_series(path)
%T7_READ_SERIES  Legge ser_<i>.txt prodotto da tb_snn_iidm_closed.v.
%
%  Righe:  k  s v vl dv accel  p_v0 p_T p_s0 p_a p_b
%          i primi 5 come bit pattern IEEE-754 esadecimale a 64 bit; i 5 parametri come STORED INTEGER
%          sfix21_En13 (quindi /8192). Ultima riga: END last collided s_finale impact_dv.
%
%  ⚠️ La conversione esadecimale passa da t7_hexread (hex2num), NON da hex2dec: quest'ultimo restituisce
%     un double e arrotonda oltre 2^53, distruggendo il confronto bit-esatto in modo silenzioso.
  assert(isfile(path), 't7_read_series: file inesistente %s', path);
  txt = readlines(path);
  txt = txt(strlength(txt) > 0);
  isEnd = startsWith(txt, "END");
  body = txt(~isEnd); tail = txt(isEnd);
  assert(numel(tail) == 1, '%s: attesa UNA riga END, trovate %d', path, numel(tail));
  n = numel(body);
  assert(n > 0, '%s: nessuna riga di serie', path);

  R = struct('k',zeros(n,1),'s',zeros(n,1),'v',zeros(n,1),'vl',zeros(n,1), ...
             'dv',zeros(n,1),'a',zeros(n,1),'params',zeros(n,5));
  for i = 1:n
    f = split(strtrim(body(i)));
    assert(numel(f) == 11, '%s riga %d: attesi 11 campi, trovati %d', path, i, numel(f));
    R.k(i)  = str2double(f(1));
    R.s(i)  = t7_hexread(f(2)); R.v(i)  = t7_hexread(f(3)); R.vl(i) = t7_hexread(f(4));
    R.dv(i) = t7_hexread(f(5)); R.a(i)  = t7_hexread(f(6));
    R.params(i,:) = str2double(f(7:11)).' / 8192.0;        % sfix21_En13
  end

  g = split(strtrim(tail(1)));
  assert(numel(g) == 5, '%s: riga END con %d campi invece di 5', path, numel(g));
  R.N        = str2double(g(2));
  R.collided = logical(str2double(g(3)));
  R.s_end    = t7_hexread(g(4));
  R.impact_dv= t7_hexread(g(5));
  assert(R.N == n, '%s: END dichiara N=%d ma le righe sono %d', path, R.N, n);
  assert(all(R.k(:).' == 1:n), '%s: indici k non consecutivi da 1', path);
end
