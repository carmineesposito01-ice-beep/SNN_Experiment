function n = gen_axi_golden(outdir, seriesdir, idx, checkBlock)
%GEN_AXI_GOLDEN  Stimoli e accel attese per la cosim AXI di T7b, dalle serie GIA' VALIDATE di T7a.
%
%  Non ricalcola nulla: legge `ser_<i>.txt` prodotti dall'anello chiuso di T7a e ne estrae
%    axi_stim_<i>.mem : 4 valori per control-step, gli ingressi che il DUT ha ricevuto,
%                       stored-integer di fixdt(1,32,20) -> 8 cifre esadecimali
%    axi_gold_<i>.mem : 1 valore per control-step, l'accel attesa in Q4.8 -> 4 cifre esadecimali
%
%  PERCHE' RIUSA LE SERIE DI T7A invece di rigenerare il golden: quelle serie sono gia' provate
%  == blocco (T7-EXACT 0/58 522). Un secondo percorso di riferimento sarebbe una seconda cosa da
%  tenere allineata, cioe' un'altra occasione di divergenza silenziosa.
%
%  checkBlock (default true): ri-piloto il BLOCCO sugli stessi ingressi e verifico che dia le stesse
%  accel. E' ridondante con T7a per costruzione — ed e' proprio per questo che va fatto: se fallisce,
%  qualcosa e' cambiato fra T7a e adesso (blocco, HDL, o le serie stesse).
  if nargin < 4 || isempty(checkBlock), checkBlock = true; end
  if ~exist(outdir,'dir'), mkdir(outdir); end
  here = fileparts(mfilename('fullpath'));
  addpath(fileparts(here));                       % per t7_read_series / t7_block_replay / t7_hexread
  FM = fimath('RoundingMethod','Floor','OverflowAction','Saturate');
  n = 0;

  for j = 1:numel(idx)
    R = t7_read_series(fullfile(seriesdir, sprintf('ser_%d.txt', idx(j))));
    N = R.N;
    % gli ingressi che il DUT ha ricevuto: stato fisico registrato dal TB, quantizzato come dal TB
    X  = double(fi([R.s(1:N).'; R.v(1:N).'; R.dv(1:N).'; R.vl(1:N).'], 1, 32, 20, FM));
    Xi = int32(round(X * 2^20));                  % stored integer di fixdt(1,32,20)
    Ai = int32(round(R.a(1:N) * 256));            % accel Q4.8 -> stored integer a 13 bit

    assert(all(abs(Ai) < 4096), 'accel fuori dai 13 bit con segno: max|Ai|=%d', max(abs(Ai)));

    if checkBlock
      A = t7_block_replay(X, 700);
      d = sum(A(:) ~= R.a(1:N));
      assert(d == 0, ['gen_axi_golden: il BLOCCO non riproduce piu'' le serie di T7a sullo scenario %d ' ...
                      '(%d disallineamenti). Qualcosa e'' cambiato: NON procedere con la cosim.'], idx(j), d);
    end

    wr(fullfile(outdir, sprintf('axi_stim_%d.mem', j)), Xi(:), 8);
    wr(fullfile(outdir, sprintf('axi_gold_%d.mem', j)), Ai(:), 4);
    n = n + 1;
  end
  fprintf('gen_axi_golden: %d scenari -> %s (verifica sul blocco: %d)\n', n, outdir, checkBlock);
end

function wr(path, v, nhex)
% stored integer con segno -> esadecimale MASCHERATO a nhex cifre.
% ⚠️ typecast di un valore NEGATIVO verso uint SATURA: va mascherato in complemento a due, altrimenti
%    tutti i valori negativi diventano 0 e il confronto fallisce su meta' del dataset (lezione T6a).
  f = fopen(path,'w');
  assert(f > 0, 'impossibile scrivere %s', path);
  m = uint64(2)^(4*nhex) - 1;
  fmt = sprintf('%%0%dX\n', nhex);
  for i = 1:numel(v)
    fprintf(f, fmt, bitand(uint64(typecast(int64(v(i)),'uint64')), m));
  end
  fclose(f);
end
