function out = build_decodedut(variant)
%BUILD_DECODEDUT  Harness L1 per il DECODE ISOLATO: I/O registrato, decode combinatorio in mezzo.
%  Misura l'Fmax PROPRIA del decode, che non e' mai stata misurata: lo sweep LUT sintetizzo' il decode
%  da solo ma registro' solo le RISORSE (LUT/FF/DSP/CARRY), non la velocita'. Serve per ACCOPPIARE il
%  decode alla profondita' di pipeline SNN giusta: comporre SNN a 99 MHz con un decode a 30 spreca
%  ~1000 FF di pipelining che il blocco non puo' usare.
%
%  variant = 'fused' | 'p3' | 'p5'
%    fused : raw_reg -> snn_decode_lut -> p_reg                       (1 stadio, com'e' oggi)
%    p3    : raw -> a | b | c -> p                                    (3 stadi)
%    p5    : raw -> a1 | a2 | b1 | b2 | c -> p                        (5 stadi, i tagli piu' fini)
%
%  Le fasi ESISTONO GIA' e sono provate bit-exact (G2 0/60000 nei round IIDM R4/R10/R12/R17): qui non
%  si progetta nulla, si misura quanto valgono da sole.
%
%  ⚠️ La MATLAB Function e' SOLA nel subsystem: con blocchi accanto scatterebbe la conversione
%     MATLAB-to-dataflow (HDL_PHASE §9). Stesso vincolo dell'harness L1 della tanh.
%  ⚠️ READ-BEFORE-WRITE: si emette il valore REGISTRATO e si calcola il nuovo dagli ingressi
%     registrati -> il path misurato e' reg -> logica -> reg, non porta -> logica.
%  ⚠️ `frac` nasce in a2 ma serve in b2: in p5 va RITARDATO di un colpo per allinearsi a b1, altrimenti
%     il probe non riproduce la struttura vera (un probe che salta il meccanismo misura altro).
  here = fileparts(mfilename('fullpath'));
  N = 64;                                  % LUT-64: la scelta e' gia' fatta, non e' un asse
  Traw = 'fi(zeros(5,1), 1, 21, 13)';      % tipo di raw (= rawl nel blocco)

  switch variant
    case 'fused'
      body = {
        '  p  = pl;'
        ['  pl = snn_decode_lut(r0, ' num2str(N) ');']
        '  r0 = raw;'};
      pers = 'r0 pl started';
      init = {['    r0 = ' Traw '; pl = snn_decode_lut(r0, ' num2str(N) ');']};
    case 'p3'
      body = {
        '  p  = pl;'
        '  pl = decode_c(s2);'
        ['  s2 = decode_b(s1k, s1f, ' num2str(N) ');']
        ['  [s1k, s1f] = decode_a(r0, ' num2str(N) ');']
        '  r0 = raw;'};
      pers = 'r0 s1k s1f s2 pl started';
      init = {['    r0 = ' Traw '; [s1k, s1f] = decode_a(r0, ' num2str(N) ');']
              ['    s2 = decode_b(s1k, s1f, ' num2str(N) '); pl = decode_c(s2);']};
    case 'p5'
      body = {
        '  p  = pl;'
        '  pl = decode_c(s4);'
        '  s4 = decode_b2(s3a, s3b, f3);'
        ['  [s3a, s3b] = decode_b1(s2k, ' num2str(N) ');']
        '  f3 = f2;                       % frac ritardato: arriva a b2 allineato con s3a/s3b'
        ['  [s2k, f2] = decode_a2(s1, ' num2str(N) ');']
        '  s1 = decode_a1(r0);'
        '  r0 = raw;'};
      pers = 'r0 s1 s2k f2 f3 s3a s3b s4 pl started';
      init = {['    r0 = ' Traw '; s1 = decode_a1(r0); [s2k, f2] = decode_a2(s1, ' num2str(N) ');']
              ['    f3 = f2; [s3a, s3b] = decode_b1(s2k, ' num2str(N) ');']
              '    s4 = decode_b2(s3a, s3b, f3); pl = decode_c(s4);'};
    case 'ph3'
      % ⚠️ MACCHINA A FASI, non pipeline: e' l'architettura VERA del blocco. Le varianti p3/p5 qui sopra
      % sono PIPELINE (ogni stadio ha il suo hardware e calcola a ogni clock) e danno 56,9 / 97,8 MHz,
      % ma il blocco ne da' 41: il probe misurava un hardware che il blocco non ha.
      % Qui un solo stadio esegue per clock, selezionato da dph, esattamente come in chart_code.
      body = {
        '  p = pl;'
        '  if dph == 1'
        ['    [q1k, q1f] = decode_a(r0, ' num2str(N) '); dph = uint8(2);']
        '  elseif dph == 2'
        ['    q2 = decode_b(q1k, q1f, ' num2str(N) '); dph = uint8(3);']
        '  elseif dph == 3'
        '    pl = decode_c(q2); dph = uint8(1); r0 = raw;'
        '  end'};
      pers = 'r0 q1k q1f q2 pl dph started';
      init = {['    r0 = ' Traw '; [q1k, q1f] = decode_a(r0, ' num2str(N) ');']
              ['    q2 = decode_b(q1k, q1f, ' num2str(N) '); pl = decode_c(q2); dph = uint8(1);']};
    case 'ph5'
      body = {
        '  p = pl;'
        '  if dph == 1'
        '    s1 = decode_a1(r0); dph = uint8(2);'
        '  elseif dph == 2'
        ['    [s2k, f2] = decode_a2(s1, ' num2str(N) '); dph = uint8(3);']
        '  elseif dph == 3'
        ['    [s3a, s3b] = decode_b1(s2k, ' num2str(N) '); f3 = f2; dph = uint8(4);']
        '  elseif dph == 4'
        '    s4 = decode_b2(s3a, s3b, f3); dph = uint8(5);'
        '  elseif dph == 5'
        '    pl = decode_c(s4); dph = uint8(1); r0 = raw;'
        '  end'};
      pers = 'r0 s1 s2k f2 f3 s3a s3b s4 pl dph started';
      init = {['    r0 = ' Traw '; s1 = decode_a1(r0); [s2k, f2] = decode_a2(s1, ' num2str(N) ');']
              ['    f3 = f2; [s3a, s3b] = decode_b1(s2k, ' num2str(N) ');']
              '    s4 = decode_b2(s3a, s3b, f3); pl = decode_c(s4); dph = uint8(1);'};
    otherwise
      error('build_decodedut:variant', 'variant = fused | p3 | p5 | ph3 | ph5');
  end

  main = [{'function p = fcn(raw)'; '%#codegen'; ['  persistent ' pers]; '  if isempty(started)'}
          init(:); {'    started = true;'; '  end'}; body(:); {'end'}];

  % i sorgenti VERI inlinati: il probe deve provare lo stesso codice che gira nel blocco
  srcs = {'snn_decode_lut','decode_a','decode_a1','decode_a2','decode_b','decode_b1','decode_b2','decode_c'};
  code = strjoin(main, newline);
  for i = 1:numel(srcs)
      code = [code newline newline fileread(fullfile(here, [srcs{i} '.m']))]; %#ok<AGROW>
  end

  out = fullfile(here, 'hdl_decode', variant);
  if exist(out,'dir'), rmdir(out,'s'); end
  bdclose('all'); mdl = ['m_dec_' variant]; if bdIsLoaded(mdl), close_system(mdl,0); end
  new_system(mdl); load_system(mdl);
  sub = [mdl '/DUT'];
  add_block('built-in/Subsystem', sub);
  add_block('simulink/User-Defined Functions/MATLAB Function', [sub '/fcn']);
  ch = sfroot().find('-isa','Stateflow.EMChart','Path',[sub '/fcn']); ch.Script = code;
  add_block('built-in/Inport',  [sub '/raw'], 'Port','1'); add_line(sub, 'raw/1', 'fcn/1');
  add_block('built-in/Outport', [sub '/p'],   'Port','1'); add_line(sub, 'fcn/1', 'p/1');
  add_block('simulink/Sources/Constant', [mdl '/i1'], 'Value','zeros(5,1)', ...
            'OutDataTypeStr','fixdt(1,21,13)', 'SampleTime','1');
  add_block('built-in/Outport', [mdl '/o1'], 'Port','1');
  add_line(mdl, 'i1/1', 'DUT/1'); add_line(mdl, 'DUT/1', 'o1/1');
  set_param(mdl, 'SolverType','Fixed-step', 'FixedStep','1', 'SolverName','FixedStepDiscrete');

  hdlset_param(mdl, 'TargetLanguage','VHDL', 'TargetDirectory', out, ...
               'GenerateHDLTestBench','off', 'HDLSubsystem', sub);
  makehdl(sub, 'TargetDirectory', out, 'TargetLanguage','VHDL', 'GenerateHDLTestBench','off');
  fprintf('DECODEDUT-OK %s -> %s\n', variant, out);
end
