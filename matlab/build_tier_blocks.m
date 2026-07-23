function build_tier_blocks()
%BUILD_TIER_BLOCKS  Aggiunge a snn_champions_lib.slx i 3 blocchi tier Donatello dello Studio Trade-off:
%  Donatello_SLOW (R2·fused), Donatello_BALANCED (R5·p3), Donatello_FAST (R9·p5), tutti in architettura
%  SPLITPIPE (registro operandi del normalize), decode-sigmoide LUT-64. Riusa i mattoni condivisi
%  (mount_split, snn_chart_code(pipe=true), dec_chart_code) — stessa logica di build_hdl_variants.
%  NON tocca gli altri blocchi. Self-contained: i sorgenti sono inlinati a build-time.
%  Gate d'accettazione: run_block_hdl_gate (G1), run_block_traj_test (G2), + firma/coerenza VHDL (G3/G4).
  here = fileparts(mfilename('fullpath'));
  cd(here);
  gen_b2_rom('Donatello');                       % ROM attiva = Donatello -> b2_rom_active.m

  % --- sorgenti VERI inlinati (single-source, letti a build-time) ---
  srcRom   = fileread(fullfile(here, 'b2_rom_active.m'));
  srcTypes = fileread(fullfile(here, 'snn_types.m'));
  % composizione decode: la chart chiama le meta' in fasi distinte -> inlinarle tutte (come build_hdl_variants)
  srcLut   = [fileread(fullfile(here, 'snn_decode_lut.m')) newline newline ...
              fileread(fullfile(here, 'decode_a.m'))  newline newline ...
              fileread(fullfile(here, 'decode_a1.m')) newline newline ...
              fileread(fullfile(here, 'decode_a2.m')) newline newline ...
              fileread(fullfile(here, 'decode_b.m'))  newline newline ...
              fileread(fullfile(here, 'decode_b1.m')) newline newline ...
              fileread(fullfile(here, 'decode_b2.m')) newline newline ...
              fileread(fullfile(here, 'decode_c.m'))  newline newline ...
              fileread(fullfile(here, 'decode_c1.m')) newline newline ...
              fileread(fullfile(here, 'decode_c2.m'))];

  d = load(fullfile(here, 'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  c = champs(find(arrayfun(@(x) strcmp(char(string(x.name)), 'Donatello'), champs), 1));
  nrm = double(c.norm(:));                        % [S V DV VL]

  %       nome                 snapshot SNN                     decode
  tiers = {'Donatello_SLOW',     'snn_variants/snn_b2_fsm_R2.m', 'fused'
           'Donatello_BALANCED', 'snn_variants/snn_b2_fsm_R5.m', 'p3'
           'Donatello_FAST',     'snn_variants/snn_b2_fsm_R9.m', 'p5'};
  NCHAMP = 64;                                     % sigmoide LUT-64 (come il deployato)

  lib = 'snn_champions_lib'; libfile = fullfile(here, [lib '.slx']);
  assert(isfile(libfile), '%s inesistente', libfile);
  if bdIsLoaded(lib), close_system(lib, 0); end
  load_system(libfile); set_param(lib, 'Lock', 'off');

  in_names  = {'s', 'v', 'dv', 'v_l'};
  out_names = {'v0', 'T', 's0', 'a', 'b'};
  for i = 1:size(tiers,1)
    name = tiers{i,1};
    snnPath = fullfile(here, tiers{i,2});
    assert(isfile(snnPath), 'snapshot SNN inesistente: %s', snnPath);
    srcFsm = fileread(snnPath);
    dec    = tiers{i,3};
    sub = [lib '/' name];
    if getSimulinkBlockHandle(sub) > 0, delete_block(sub); end
    add_block('built-in/Subsystem', sub, 'Position', [40, 300 + (i-1)*80, 230, 340 + (i-1)*80], ...
              'Description', tier_description(name, dec));
    % SPLITPIPE: snn_chart_code(...,true) = registro operandi ; dec_chart_code = macchina a fasi del decode
    mount_split(sub, in_names, out_names, ...
      snn_chart_code(srcRom, srcTypes, srcFsm, nrm, true), ...
      dec_chart_code(srcLut, dec, NCHAMP, 'shared'));
    fprintf('  costruito %s [splitpipe, decode=%s]\n', name, dec);
  end

  set_param(lib, 'EnableLBRepository', 'on');
  save_system(lib, libfile);
  close_system(lib, 0);
  fprintf('OK: 3 blocchi tier SELF-CONTAINED HDL-ready (splitpipe) aggiunti a %s.slx\n', lib);
end


function d = tier_description(name, dec)
%TIER_DESCRIPTION  Testo della Description del blocco tier (Block Properties in Simulink).
  cfg = struct('Donatello_SLOW','R2 (SNN 2 stadi) + decode fused  -> tier AREA MINIMA (~30 MHz io-timed)', ...
               'Donatello_BALANCED','R5 (SNN 5 stadi) + decode p3  -> tier COMPROMESSO (~58 MHz io-timed)', ...
               'Donatello_FAST','R9 (SNN 9 stadi) + decode p5      -> tier MARGINE MASSIMO (~74 MHz io-timed)');
  L = {
    sprintf('%s - SNN car-following (champion Donatello), architettura SPLITPIPE (SNN+decode come due', name)
    'entita'' di sintesi, con registro sugli operandi del normalize). Tier dello Studio Trade-off (Blocco A).'
    ''
    sprintf('CONFIGURAZIONE: %s', cfg.(name))
    'Decode della sigmoide via LUT a 64 punti. I tre tier danno gli STESSI 5 parametri (bit-exact fra loro),'
    'differiscono per latenza (342/364/406 clock) e profilo di risorse/Fmax.'
    ''
    'INGRESSI (fisici, fixed >=20 bit frazionari): s [m], v [m/s], dv [m/s] (sat +-20), v_l [m/s].'
    'USCITE (parametri IDM): v0, T, s0, a, b.  1 campione = 1 inferenza (edge-triggered), niente start/done.'
    ''
    'SELF-CONTAINED: nessun .m esterno; HDL Coder genera il VHDL dal solo blocco (time-mux, DualPortRAM).'
    'VERIFICHE: run_block_hdl_gate (self-contained) · run_block_traj_test (dmax=0).'
    'Rigenerazione: build_tier_blocks.m (NON modificare la chart a mano).'
  };
  d = strjoin(L, newline);
end
