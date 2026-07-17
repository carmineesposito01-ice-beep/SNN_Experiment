function Kout = cl_export_plant_par(trajIdx, K, hold, od)
%CL_EXPORT_PLANT_PAR  [Fase B2.0-2a-M2 B.2] Esporta i vettori dell'anello di riferimento per il testbench
%  Verilog: leader (xl,vl), accel di riferimento, e il golden xq (s,v,dv) — tutti come DOUBLE bit-esatti
%  (IEEE-754, num2hex -> 16 hex -> $bitstoreal nel TB). PLANT-PAR usa questi per verificare che il plant
%  riprodotto nel TB (real) == il plant di riferimento (cl_ref_acciidm_m), fed la stessa accel, SENZA RTL.
  if nargin < 4 || isempty(od), od = fullfile(fileparts(mfilename('fullpath')),'axi','acciidm_m'); end
  ref = cl_ref_acciidm_m(trajIdx, K, hold, 'train');
  Kout = numel(ref.s);
  if ~exist(od,'dir'), mkdir(od); end
  wr = @(f,v) writehex(fullfile(od,f), v);
  wr('cl_xl.mem', ref.xl);    wr('cl_vl.mem', ref.vl);    wr('cl_accel.mem', ref.accel);
  wr('cl_golds.mem', ref.s);  wr('cl_goldv.mem', ref.v);  wr('cl_golddv.mem', ref.dv);
  fc = fopen(fullfile(od,'cl_const.mem'),'w');             % s_lo, v_cap, xe0, ve0 (in quest'ordine)
  fprintf(fc,'%s\n', num2hex(ref.s_lo)); fprintf(fc,'%s\n', num2hex(ref.v_cap));
  fprintf(fc,'%s\n', num2hex(ref.xe0));  fprintf(fc,'%s\n', num2hex(ref.ve0));
  fclose(fc);
  save(fullfile(od,'cl_meta.mat'), 'Kout', 'trajIdx');
  fprintf('cl_export_plant_par: traj %d, %d control-step -> %s\n', trajIdx, Kout, od);
end

function writehex(f, v)
  fid = fopen(f,'w');
  for i = 1:numel(v), fprintf(fid,'%s\n', num2hex(v(i))); end   % IEEE-754 double -> 16 hex
  fclose(fid);
end
