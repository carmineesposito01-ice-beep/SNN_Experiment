function res = rtl_run_xsim(od, hdlsrc, tag, K, HOLD)
%RTL_RUN_XSIM  Invoca run_xsim_champion.sh e fa il parse di RTLRES. Helper condiviso da run_rtl_validate
%  e sensitivity_A1. Ritorna struct {nMismatch, n, firstbad}.
  cmd = sprintf('bash run_xsim_champion.sh "%s" %d %d stim_%s.mem gold_%s.mem', ...
                strrep(hdlsrc,'\','/'), K, HOLD, tag, tag);
  [~, out] = system(['cd /d "' od '" && ' cmd]);
  tok = regexp(out, 'RTLRES nMismatch=(\d+) n=(\d+) firstbad=(-?\d+)', 'tokens', 'once');
  assert(~isempty(tok), 'xsim non ha prodotto RTLRES. Output:\n%s', out);
  res = struct('nMismatch', str2double(tok{1}), 'n', str2double(tok{2}), 'firstbad', str2double(tok{3}));
end
