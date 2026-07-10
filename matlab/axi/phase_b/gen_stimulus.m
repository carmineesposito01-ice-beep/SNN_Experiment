function gen_stimulus()
%GEN_STIMULUS  Stimoli xn (Q5.13, 19-bit) per il SAIF del B2: tipico + worst.
%  Tipico = traiettoria reale 1 (following normale). Worst = la traiettoria reale
%  con la maggiore dinamica di Δv (proxy di alto firing; onesto, non valori sintetici).
%  snn_normalize(x_phys, norm) con norm=[S V DV VL] di Donatello (=[150 40 20 40]).
%  Scrive .mem: 4 parole 19-bit esadecimali per riga (una riga = un campione temporale).
  here  = fileparts(mfilename('fullpath'));
  mroot = fileparts(fileparts(here));            % .../matlab
  addpath(mroot);
  d = load(fullfile(mroot, 'champions_export.mat')); ch = d.champions;
  if iscell(ch), ch = [ch{:}]; end
  idx  = find(arrayfun(@(x) strcmp(char(string(x.name)), 'Donatello'), ch), 1);
  norm = double(ch(idx).norm(:));                % [S V DV VL]

  t   = load(fullfile(mroot, 'test_trajectories.mat'));
  trs = t.trajectories;                          % cell 6x1, ogni {k}.val = 4xN

  writeStim(fullfile(here, 'stim_typical.mem'), double(trs{1}.val), norm);

  sd = cellfun(@(c) std(double(c.val(3, :))), trs);   % dinamica di dv per traiettoria
  [~, iw] = max(sd);
  writeStim(fullfile(here, 'stim_worst.mem'), double(trs{iw}.val), norm);

  fprintf('OK: typical=traj1, worst=traj%d (std(dv)=%.2f), %d righe/traj\n', ...
          iw, sd(iw), size(trs{1}.val, 2));
end

function writeStim(fname, X, norm)
  N = size(X, 2);
  fid = fopen(fname, 'w');
  for i = 1:N
    xn = snn_normalize(X(:, i), norm);           % 4x1 double normalizzato
    row = '';
    for j = 1:4
      q = round(xn(j) * 8192);                   % Q5.13
      q = max(min(q, 2^18 - 1), -2^18);          % satura a 19-bit con segno
      q = mod(q, 2^19);                          % due complementi 19-bit
      row = [row sprintf('%05X ', uint32(q))];   %#ok<AGROW>
    end
    fprintf(fid, '%s\n', strtrim(row));
  end
  fclose(fid);
end
