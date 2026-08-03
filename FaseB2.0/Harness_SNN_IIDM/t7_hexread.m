function x = t7_hexread(h)
%T7_HEXREAD  16 cifre esadecimali (bit pattern IEEE-754) -> double, SENZA perdita.
%
%  ⚠️ NON usare `typecast(uint64(hex2dec(h)),'double')`: `hex2dec` restituisce un DOUBLE, quindi un
%  valore a 64 bit maggiore di 2^53 viene ARROTONDATO prima del typecast. Il difetto e' silenzioso
%  nella magnitudine (~1e-12 su valori di ordine 30) ma distrugge il confronto BIT-ESATTO, e in T7a
%  faceva fallire PLANT-PAR con 2241/2400 disallineamenti su un plant perfettamente corretto.
%  MATLAB ha la funzione apposita: `hex2num`.
%
%  h : string/char/cellstr di 16 cifre esadecimali
%  x : double con lo STESSO bit pattern
  if isstring(h) || iscellstr(h) %#ok<ISCLSTR>
    x = zeros(numel(h),1);
    for i = 1:numel(h), x(i) = hex2num(char(h(i))); end
  else
    x = hex2num(char(h));
  end
end
