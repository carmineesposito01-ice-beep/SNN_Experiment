function build_hdl_variants()
%BUILD_HDL_VARIANTS  Aggiunge a snn_champions_lib.slx 6 blocchi Donatello_LUT{N} (N=16..512):
%  forward B2 time-multiplexato (snn_b2_fsm, ROM Donatello) + decode sigmoide via LUT a N punti
%  (snn_decode_lut). Blocchi STREAMING HDL-ready, porte  xn(4)+start -> params(5)+done.
%  I 6 blocchi differiscono SOLO per N (dimensione LUT del decode); il forward e' identico.
%
%  Stile REFERENZIATO (come il B2 deployato): la MATLAB Function chiama snn_b2_fsm e
%  snn_decode_lut -> questi (+ snn_types, b2_rom_active) devono stare sul path all'uso/sim/HDL.
%  ROM Donatello via gen_b2_rom('Donatello') -> b2_rom_active (usata da snn_b2_fsm).
%  Idempotente: se i blocchi esistono gia', li rigenera. NON tocca i 4 blocchi base.
  here = fileparts(mfilename('fullpath'));
  gen_b2_rom('Donatello');                          % ROM attiva = Donatello
  lib = 'snn_champions_lib';
  libfile = fullfile(here, [lib '.slx']);
  assert(isfile(libfile), '%s inesistente: esegui prima build_library()', libfile);
  if bdIsLoaded(lib), close_system(lib, 0); end
  load_system(libfile);
  set_param(lib, 'Lock', 'off');                    % libreria bloccata di default -> sblocca per editare

  Ns = [16 32 64 128 256 512];
  in_names  = {'xn1', 'xn2', 'xn3', 'xn4'};
  out_names = {'v0', 'T', 's0', 'a', 'b'};
  for iN = 1:numel(Ns)
    N = Ns(iN); name = sprintf('Donatello_LUT%d', N); sub = [lib '/' name];
    if getSimulinkBlockHandle(sub) > 0, delete_block(sub); end   % idempotente
    add_block('built-in/Subsystem', sub, ...
              'Position', [40, 30 + (iN-1)*80, 200, 70 + (iN-1)*80]);
    add_block('simulink/User-Defined Functions/MATLAB Function', [sub '/SNN']);
    chart = sfroot().find('-isa', 'Stateflow.EMChart', 'Path', [sub '/SNN']);
    chart.Script = lut_block_code(N);
    add_block('simulink/Signal Routing/Mux',   [sub '/mux'],   'Inputs',  '4');
    add_block('simulink/Signal Routing/Demux', [sub '/demux'], 'Outputs', '5');
    for j = 1:4                                      % xn(4) -> mux -> SNN in1
      add_block('built-in/Inport', [sub '/' in_names{j}], 'Port', num2str(j));
      add_line(sub, [in_names{j} '/1'], ['mux/' num2str(j)]);
    end
    add_block('built-in/Inport', [sub '/start'], 'Port', '5');   % start -> SNN in2
    add_line(sub, 'mux/1',   'SNN/1');
    add_line(sub, 'start/1', 'SNN/2');
    add_line(sub, 'SNN/1', 'demux/1');              % params(5) -> demux -> 5 outport
    for j = 1:5
      add_block('built-in/Outport', [sub '/' out_names{j}], 'Port', num2str(j));
      add_line(sub, ['demux/' num2str(j)], [out_names{j} '/1']);
    end
    add_block('built-in/Outport', [sub '/done'], 'Port', '6');   % done -> outport 6
    add_line(sub, 'SNN/2', 'done/1');
  end
  set_param(lib, 'EnableLBRepository', 'on');
  save_system(lib, libfile);
  close_system(lib, 0);
  fprintf('Aggiunti %d blocchi Donatello_LUT{N} a %s.slx (N = %s)\n', ...
          numel(Ns), lib, mat2str(Ns));
end


function code = lut_block_code(N)
%LUT_BLOCK_CODE  Testo della MATLAB Function referenziata per il blocco Donatello_LUT{N}.
%  Forward B2 streaming (snn_b2_fsm) + decode LUT-N (snn_decode_lut). params latch su valid.
  L = {
    'function [params, done] = SNN(xn, start)'
    '%#codegen'
    '% Donatello streaming: snn_b2_fsm (ROM Donatello) + snn_decode_lut(raw, N).'
    '% xn = 4x1 NORMALIZZATO ; start=1 avvia una control-step ; done=1 -> params pronti.'
    '  Tv = snn_types(''fixed'', 13);'
    '  [raw, valid] = snn_b2_fsm(cast(xn, ''like'', Tv.V), start);'
    '  persistent preg'
    '  if isempty(preg)'
    '    preg = fi(zeros(5,1), numerictype(1,21,13));'
    '  end'
    '  if valid'
    ['    preg = snn_decode_lut(raw, ' num2str(N) ');']
    '  end'
    '  params = preg;'
    '  done   = valid;'
    'end'
  };
  code = strjoin(L, newline);
end
