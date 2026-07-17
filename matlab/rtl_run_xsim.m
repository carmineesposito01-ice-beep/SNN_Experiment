function res = rtl_run_xsim(od, hdlsrc, tag, K, HOLD, script)
%RTL_RUN_XSIM  Invoca il runner xsim (default run_xsim_champion.sh; Harness B passa run_xsim_acciidm_m.sh)
%  e fa il parse di RTLRES. Helper condiviso. Ritorna struct {nMismatch, n, firstbad}.
  if nargin < 6 || isempty(script), script = 'run_xsim_champion.sh'; end
  cmd = sprintf('bash %s "%s" %d %d stim_%s.mem gold_%s.mem', ...
                script, strrep(hdlsrc,'\','/'), K, HOLD, tag, tag);
  [~, out] = system(['cd /d "' od '" && ' cmd]);
  tok = regexp(out, 'RTLRES nMismatch=(\d+) n=(\d+) firstbad=(-?\d+)', 'tokens', 'once');
  assert(~isempty(tok), 'xsim non ha prodotto RTLRES. Output:\n%s', out);
  res = struct('nMismatch', str2double(tok{1}), 'n', str2double(tok{2}), 'firstbad', str2double(tok{3}));
end
