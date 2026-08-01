function p2_write_json(path, R)
%P2_WRITE_JSON  Scrive l'artefatto di P2-EXACT nella stessa forma degli altri della Fase C:
%  {"data": ..., "prov": {...}}, cosi' `./run_phase_c.sh summary` lo elenca come gli altri e la
%  provenienza si legge allo stesso modo.
  prov = struct('timestamp', datestr(now, 'yyyy-mm-ddTHH:MM:SS'), ...
                'frontend', 'matlab', ...
                'bitstream_sig', 'n/a (P2 e'' simulazione RTL)', ...
                'sorgente', 'rtl-xsim + blocco Simulink', ...
                'cwd', pwd);
  obj = struct('data', R, 'prov', prov);
  fid = fopen(path, 'w');
  assert(fid > 0, 'p2_write_json: impossibile aprire %s', path);
  fwrite(fid, jsonencode(obj, 'PrettyPrint', true));
  fclose(fid);
end
