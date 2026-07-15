function build_hdl_variants()
%BUILD_HDL_VARIANTS  Aggiunge a snn_champions_lib.slx i blocchi Donatello HDL-ready SELF-CONTAINED:
%  `Donatello_Champion` (decode deployato, sigma-LUT 256) + `Donatello_LUT{16..512}` (decode LUT-N).
%
%  ARCHITETTURA = quella del bitstream: forward B2 **time-mux** (snn_b2_fsm, hdl.RAM, 1 neurone/clock)
%  -> HDL Coder genera il time-mux (DualPortRAM), non la parallela superata (HDL_PHASE §3.1.1).
%
%  I/O **FISICO** (fixed): s, v, dv, v_l -> v0, T, s0, a, b. **NIENTE start/done**: la FSM e' pilotata
%  internamente (free-running: riparte su done) -> plug&play e nessun fallimento silenzioso (§3.1.2).
%
%  SELF-CONTAINED: la chart inlina come **funzioni locali** i sorgenti VERI, letti a build-time
%  (b2_rom_active + snn_types + snn_b2_fsm + il decode). Le funzioni locali hanno precedenza sul path
%  => nessuna copia a mano (niente deriva) e il `.slx` gira/genera VHDL **su un altro PC senza alcun .m**.
%  Gate d'accettazione: `run_block_hdl_gate` (toglie matlab/ dal path e lancia makehdl).
%
%  USO: il time-mux impiega ~341 clock/inferenza -> il modello ospite gira al **rate di clock** e i
%  params si aggiornano ogni ~341 passi. E' l'architettura (il 5,5x di area risparmiata), non un difetto.
  here = fileparts(mfilename('fullpath'));
  gen_b2_rom('Donatello');                       % ROM attiva = Donatello -> b2_rom_active.m

  % --- sorgenti VERI da inlinare (single-source: letti, non copiati) ---
  srcRom   = fileread(fullfile(here, 'b2_rom_active.m'));
  srcTypes = fileread(fullfile(here, 'snn_types.m'));
  srcFsm   = fileread(fullfile(here, 'snn_b2_fsm.m'));
  srcLut   = fileread(fullfile(here, 'snn_decode_lut.m'));
  srcHdl   = fileread(fullfile(here, 'snn_decode_hdl.m'));

  d = load(fullfile(here, 'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  c = champs(find(arrayfun(@(x) strcmp(char(string(x.name)), 'Donatello'), champs), 1));
  nrm = double(c.norm(:));                       % [S V DV VL]

  Ns = [16 32 64 128 256 512];
  names = [{'Donatello_Champion'}, arrayfun(@(N) sprintf('Donatello_LUT%d', N), Ns, 'UniformOutput', false)];
  calls = [{'snn_decode_hdl(raw)'}, arrayfun(@(N) sprintf('snn_decode_lut(raw, %d)', N), Ns, 'UniformOutput', false)];
  decs  = [{srcHdl}, repmat({srcLut}, 1, numel(Ns))];

  lib = 'snn_champions_lib'; libfile = fullfile(here, [lib '.slx']);
  assert(isfile(libfile), '%s inesistente: esegui prima build_library()', libfile);
  if bdIsLoaded(lib), close_system(lib, 0); end
  load_system(libfile); set_param(lib, 'Lock', 'off');

  in_names  = {'s', 'v', 'dv', 'v_l'};
  out_names = {'v0', 'T', 's0', 'a', 'b'};
  for i = 1:numel(names)
    sub = [lib '/' names{i}];
    if getSimulinkBlockHandle(sub) > 0, delete_block(sub); end
    add_block('built-in/Subsystem', sub, 'Position', [40, 30 + (i-1)*80, 230, 70 + (i-1)*80]);
    add_block('simulink/User-Defined Functions/MATLAB Function', [sub '/SNN']);
    chart = sfroot().find('-isa', 'Stateflow.EMChart', 'Path', [sub '/SNN']);
    chart.Script = chart_code(calls{i}, decs{i}, srcRom, srcTypes, srcFsm, nrm);
    for j = 1:4
      add_block('built-in/Inport', [sub '/' in_names{j}], 'Port', num2str(j));
      add_line(sub, [in_names{j} '/1'], ['SNN/' num2str(j)]);
    end
    for j = 1:5
      add_block('built-in/Outport', [sub '/' out_names{j}], 'Port', num2str(j));
      add_line(sub, ['SNN/' num2str(j)], [out_names{j} '/1']);
    end
    fprintf('  costruito %s\n', names{i});
  end
  set_param(lib, 'EnableLBRepository', 'on');
  save_system(lib, libfile);
  close_system(lib, 0);
  fprintf('OK: %d blocchi SELF-CONTAINED (time-mux, I/O fisico, no start/done) in %s.slx\n', numel(names), lib);
end


function code = chart_code(decodeCall, srcDecode, srcRom, srcTypes, srcFsm, nrm)
%CHART_CODE  Testo della chart: main + normalize locale + i sorgenti VERI come funzioni locali.
  M = @(x) sprintf('%.17g', x);
  L = {
    'function [v0, T, s0, a, b] = SNN(s, v, dv, v_l)'
    '%#codegen'
    '% Donatello TIME-MUX (l''architettura del bitstream) - SELF-CONTAINED: zero dipendenze .m.'
    '%  I/O FISICO (fixed): s,v,dv,v_l -> v0,T,s0,a,b.  NIENTE start/done: FSM pilotata internamente.'
    '%  ~341 clock/inferenza (1 neurone/clock) -> i params si aggiornano ogni ~341 passi.'
    '  Tt = snn_types(''fixed'', 13);'
    '  xn = local_normalize(s, v, dv, v_l, Tt);'
    '  persistent pv xprev started'
    '  if isempty(started)'
    '    pv = fi(zeros(5,1), 1, 21, 13);'
    '    xprev = xn; started = true;'
    '    go = true;                       % 1a inferenza all''avvio'
    '  else'
    '    % EDGE-TRIGGERED sul cambio d''ingresso: 1 campione = 1 inferenza, per QUALUNQUE hold >= 341'
    '    % clock. (Free-running sarebbe sbagliato: con hold>341 farebbe piu'' inferenze sullo stesso'
    '    %  ingresso e lo stato evolverebbe troppo in fretta.)'
    '    go = any(xn ~= xprev);'
    '  end'
    '  xprev = xn;'
    '  [raw, valid] = snn_b2_fsm(xn, go);'
    '  if valid'
    ['    pv = ' decodeCall ';']
    '  end'
    '  v0 = pv(1); T = pv(2); s0 = pv(3); a = pv(4); b = pv(5);'
    'end'
    ''
    'function xn = local_normalize(s, v, dv, v_l, T)'
    '%LOCAL_NORMALIZE  fisico -> xn (fixed). Nel deployato la normalize gira in SW float e all''HDL'
    '%  arriva gia'' xn (HDL_PHASE §3.1); qui sta nel blocco per avere I/O fisico.'
    '%  RECIPROCI a Q?.30 (NON Q?.20): verificato che con Q?.20 l''arrotondamento di xn devia di 1 LSB'
    '%  dal path float ~1 volta su 25 step -> uno spike flippa -> i params divergono. Con Q?.30 e'
    '%  ingressi con >=20 bit frazionari, xn e'' IDENTICO al riferimento float (0 diff).'
    ['  invS   = fi(' M(1/nrm(1))      ', 1, 34, 30);']
    ['  invV   = fi(' M(1/nrm(2))      ', 1, 34, 30);']
    ['  inv2DV = fi(' M(1/(2*nrm(3)))  ', 1, 34, 30);']
    ['  invVL  = fi(' M(1/nrm(4))      ', 1, 34, 30);']
    ['  DVc    = fi(' M(nrm(3)) ', 1, 24, 13);   % 24-13-1 = 10 bit interi: DV=' M(nrm(3)) ' ci sta']
    '                                     % (con Q5.13/18bit saturerebbe a ~16 -> clamp sbagliato)'
    '  d = dv;                            % clamp a +-DV. NB: d(:) = ... per NON cambiare il tipo di d'
    '  if d >  DVc, d(:) =  DVc; end      %     (codegen: una variabile non puo'' cambiare tipo, HDL_PHASE §9)'
    '  if d < -DVc, d(:) = -DVc; end'
    '  xn = cast(zeros(4,1), ''like'', T.V);'
    '  xn(1) = cast(s * invS, ''like'', T.V);'
    '  xn(2) = cast(v * invV, ''like'', T.V);'
    '  xn(3) = cast((d + DVc) * inv2DV, ''like'', T.V);'
    '  xn(4) = cast(v_l * invVL, ''like'', T.V);'
    'end'
    ''
    '% ===================================================================================='
    '% Funzioni locali INLINATE dai sorgenti veri (build_hdl_variants le legge a build-time).'
    '% Le funzioni locali hanno precedenza sul path => il blocco e'' SELF-CONTAINED.'
    '% NON modificarle qui: si rigenerano con build_hdl_variants.'
    '% ===================================================================================='
  };
  code = strjoin(L, newline);
  code = [code newline newline srcRom newline newline srcTypes newline newline srcFsm newline newline srcDecode];
end
