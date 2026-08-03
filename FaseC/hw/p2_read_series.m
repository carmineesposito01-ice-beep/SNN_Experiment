function S = p2_read_series(path, nveh)
%P2_READ_SERIES  Legge ser_<i>.txt prodotto da tb_platoon.v.
%
%  Righe:  t  i  gap  v  x  a  dv  vl        (i = indice veicolo, 0-based)
%          i sei valori come bit pattern IEEE-754 esadecimale a 64 bit.
%  Ultima riga: END K collided.
%
%  ⚠️ La conversione passa da t7_hexread (hex2num), NON da hex2dec: quest'ultimo restituisce un
%     double e arrotonda oltre 2^53, distruggendo il confronto bit-esatto IN SILENZIO. In T7a
%     questo difetto faceva fallire PLANT-PAR con 2241/2400 disallineamenti su un plant corretto.
%
%  S : struct con campi (K x nveh): gap, v, x, a, dv, vl  +  K, collided

  here = fileparts(mfilename('fullpath'));
  addpath(fullfile(here, '..', '..', 'FaseB2.0', 'Harness_SNN_IIDM'));  % t7_hexread

  txt = strsplit(strtrim(fileread(path)), newline);
  tail = txt(startsWith(strtrim(txt), 'END'));
  assert(numel(tail) == 1, '%s: attesa UNA riga END, trovate %d', path, numel(tail));
  ft = strsplit(strtrim(tail{1}));
  K = str2double(ft{2}); collided = str2double(ft{3});

  body = txt(~startsWith(strtrim(txt), 'END'));
  body = body(~cellfun(@isempty, strtrim(body)));
  assert(numel(body) == K*nveh, ...
         '%s: attese %d righe di serie (K=%d x nveh=%d), trovate %d', ...
         path, K*nveh, K, nveh, numel(body));

  nomi = {'gap','v','x','a','dv','vl'};
  for c = 1:numel(nomi), S.(nomi{c}) = zeros(K, nveh); end

  for r = 1:numel(body)
    f = strsplit(strtrim(body{r}));
    assert(numel(f) == 8, '%s riga %d: attesi 8 campi, trovati %d', path, r, numel(f));
    t = str2double(f{1}) + 1;              % 0-based nel file -> 1-based in MATLAB
    j = str2double(f{2}) + 1;
    for c = 1:numel(nomi)
      S.(nomi{c})(t, j) = t7_hexread(f{2 + c});
    end
  end
  S.K = K; S.collided = logical(collided); S.nveh = nveh;
end
