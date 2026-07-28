function probe_two_mf()
%PROBE_TWO_MF  [SPLIT Fase 0] Make-or-break: DUE MATLAB Function con `persistent` CIASCUNA, nello
%  STESSO subsystem, collegate da un segnale. Genera VHDL, oppure la conversione MATLAB-to-dataflow
%  scatta e VIETA i persistent fuori dall'entry point (HDL_PHASE.md §9)?
%
%  Se genera -> la separazione SNN|decode e' possibile e si procede con la Fase 1.
%  Se NON genera -> l'approccio e' morto: si e' speso 20 min invece di 2 ore.
%
%  ⚠️ Il probe e' MINIMALE apposta: due funzioni banali (un accumulatore e un ritardo), non il decode
%  vero. Prova SOLO se "due MF con persistent nello stesso subsystem" e' ammesso da HDL Coder. Se lo e',
%  il contenuto vero della Fase 1 e' un dettaglio; se non lo e', nessun contenuto puo' salvarlo.
  here = fileparts(mfilename('fullpath')); cd(here);
  out = fullfile(here, 'hdl_probe_split'); if exist(out,'dir'), rmdir(out,'s'); end

  % --- MF 1: accumulatore (un persistent) ---
  codeA = strjoin({
    'function y = mfA(x)'
    '%#codegen'
    '  persistent acc'
    '  if isempty(acc), acc = int16(0); end'
    '  y = acc;'
    '  acc = acc + x;'
    'end'}, newline);
  % --- MF 2: ritardo di un colpo (un persistent) ---
  codeB = strjoin({
    'function z = mfB(y)'
    '%#codegen'
    '  persistent prev'
    '  if isempty(prev), prev = int16(0); end'
    '  z = prev;'
    '  prev = y;'
    'end'}, newline);

  bdclose('all'); mdl = 'm_probe_split'; if bdIsLoaded(mdl), close_system(mdl,0); end
  new_system(mdl); load_system(mdl);
  sub = [mdl '/DUT'];
  add_block('built-in/Subsystem', sub);

  % le DUE MF nello stesso subsystem, in catena: x -> mfA -> mfB -> z
  add_block('simulink/User-Defined Functions/MATLAB Function', [sub '/A']);
  chA = sfroot().find('-isa','Stateflow.EMChart','Path',[sub '/A']); chA.Script = codeA;
  add_block('simulink/User-Defined Functions/MATLAB Function', [sub '/B']);
  chB = sfroot().find('-isa','Stateflow.EMChart','Path',[sub '/B']); chB.Script = codeB;

  add_block('built-in/Inport',  [sub '/x'], 'Port','1'); add_line(sub, 'x/1', 'A/1');
  add_line(sub, 'A/1', 'B/1');                             % il segnale che attraversa il confine
  add_block('built-in/Outport', [sub '/z'], 'Port','1'); add_line(sub, 'B/1', 'z/1');

  add_block('simulink/Sources/Constant', [mdl '/i1'], 'Value','1', ...
            'OutDataTypeStr','int16', 'SampleTime','1');
  add_block('built-in/Outport', [mdl '/o1'], 'Port','1');
  add_line(mdl, 'i1/1', 'DUT/1'); add_line(mdl, 'DUT/1', 'o1/1');
  set_param(mdl, 'SolverType','Fixed-step', 'FixedStep','1', 'SolverName','FixedStepDiscrete');

  hdlset_param(mdl, 'TargetLanguage','VHDL', 'TargetDirectory', out, ...
               'GenerateHDLTestBench','off', 'HDLSubsystem', sub);
  ok = false; msg = '';
  try
    makehdl(sub, 'TargetDirectory', out, 'TargetLanguage','VHDL', 'GenerateHDLTestBench','off');
    v = dir(fullfile(out, '**', '*.vhd'));
    ok = ~isempty(v);
    % ⚠️ il cancello e' il FILE, non l'assenza di eccezione: makehdl puo' non lanciare e non produrre.
    if ok
        names = {v.name};
        fprintf('PROBE-SPLIT OK: %d file .vhd\n', numel(v));
        for k = 1:numel(v), fprintf('  %s\n', names{k}); end
        % due MF distinte -> due entity? (o HDL Coder le fonde)
        fprintf('PROBE-SPLIT entity con "A"/"B" nel nome: A=%d B=%d\n', ...
                sum(contains(names,'A')), sum(contains(names,'B')));
    end
  catch ME
    msg = ME.message;
  end
  if ~ok
      fprintf('PROBE-SPLIT FALLITO: %s\n', msg);
      fprintf('  -> se il messaggio cita dataflow / persistent, l''approccio SPLIT e'' morto.\n');
  end
end
