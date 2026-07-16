function build_acc_sweep_mex(Ns)
%BUILD_ACC_SWEEP_MEX  Genera i MEX del kernel dello sweep, UNO per recipN (la LUT e' coder.const).
%  Ns (opz.) = i recipN >0 da costruire; 0 (riferimento divide()) e' sempre incluso.
  if nargin < 1 || isempty(Ns), Ns = [16 32 64 128 256]; end
  here = fileparts(mfilename('fullpath')); addpath(here);
  cfg = coder.config('mex'); cfg.GenerateReport = false;
  valt = coder.typeof(zeros(4, 1), [4 Inf], [false true]);   % 4 x N (lunghezza variabile)
  Rt   = coder.typeof(zeros(1, 5), [Inf 5], [true false]);   % N x 5
  for N = [0, Ns(:).']
    codegen('acc_sweep_kernel', '-config', cfg, ...
            '-args', {valt, Rt, coder.Constant(N)}, ...
            '-o', sprintf('acc_sweep_kernel_r%d_mex', N));
    fprintf('OK acc_sweep_kernel_r%d_mex\n', N);
  end
end
