function [pers, dec, unused, ini] = decode_phase_code(decVariant, N)
%DECODE_PHASE_CODE  [SPLIT] FONTE UNICA della macchina a fasi del decode. La usano SIA chart_code (che
%  vi aggiunge la logica SNN e i persistent xprev/started) SIA dec_chart_code (che la isola in una MF).
%  Duplicarla farebbe divergere le due architetture alla prima modifica -> single source.
%
%  Ritorna:
%    pers  — i persistent del SOLO decode (rawl + eventuali stadi + dph/dodec). NON include pv/xprev/started.
%    dec   — le righe che eseguono una fase per ciclo + il latch di rawl su `valid`.
%    ini   — l'inizializzazione dei persistent del decode (rawl e stadi). NON include `pv = ...`.
%    unused — [] (segnaposto per compat. con l'estrazione a 4 valori).
%  ⚠️ ORDINE VINCOLANTE (vedi chart_code): la catena legge `rawl` PRIMA del latch -> campione PRECEDENTE.
  unused = [];
  decodeCall = sprintf('snn_decode_lut(rawl, %d)', N);
  switch decVariant
    case 'fused'
      pers = 'rawl dodec';
      ini  = {'    rawl = fi(zeros(5,1), 1, 21, 13);'
              '    dodec = false;'};
      dec  = {'  if dodec'
              ['    pv = ' decodeCall ';']
              '    dodec = false;'
              '  end'
              '  if valid'
              '    rawl(:) = raw;               % latch DOPO la catena: rawl e'' un vero registro'
              '    dodec = true;'
              '  end'};
    case 'p3'
      pers = 'rawl dph q1k q1f q2';
      ini  = {'    rawl = fi(zeros(5,1), 1, 21, 13);'
              ['    [q1k, q1f] = decode_a(rawl, ' num2str(N) ');']
              ['    q2 = decode_b(q1k, q1f, ' num2str(N) ');']
              '    dph = uint8(0);'};
      dec  = {'  if dph == 1'
              ['    [q1k, q1f] = decode_a(rawl, ' num2str(N) '); dph = uint8(2);']
              '  elseif dph == 2'
              ['    q2 = decode_b(q1k, q1f, ' num2str(N) '); dph = uint8(3);']
              '  elseif dph == 3'
              '    pv = decode_c(q2); dph = uint8(0);'
              '  end'
              '  if valid'
              '    rawl(:) = raw; dph = uint8(1);'
              '  end'};
    case 'p5'
      pers = 'rawl dph s1 s2k f2 f3 s3a s3b s4';
      ini  = {'    rawl = fi(zeros(5,1), 1, 21, 13);'
              '    s1 = decode_a1(rawl);'
              ['    [s2k, f2] = decode_a2(s1, ' num2str(N) ');']
              '    f3 = f2;'
              ['    [s3a, s3b] = decode_b1(s2k, ' num2str(N) ');']
              '    s4 = decode_b2(s3a, s3b, f3);'
              '    dph = uint8(0);'};
      % ⚠️ `frac` (f2) nasce in a2 e serve in b2: va RITARDATO (f3) per arrivare allineato con s3a/s3b.
      dec  = {'  if dph == 1'
              '    s1 = decode_a1(rawl); dph = uint8(2);'
              '  elseif dph == 2'
              ['    [s2k, f2] = decode_a2(s1, ' num2str(N) '); dph = uint8(3);']
              '  elseif dph == 3'
              ['    [s3a, s3b] = decode_b1(s2k, ' num2str(N) '); f3 = f2; dph = uint8(4);']
              '  elseif dph == 4'
              '    s4 = decode_b2(s3a, s3b, f3); dph = uint8(5);'
              '  elseif dph == 5'
              '    pv = decode_c(s4); dph = uint8(0);'
              '  end'
              '  if valid'
              '    rawl(:) = raw; dph = uint8(1);'
              '  end'};
    case 'p6'
      % [A3] come p5, ma decode_c SPEZZATA fra prodotti (c1) e somma+cast (c2). Controproducente sul
      % timing (a_fast6 = 38,1 MHz), resta disponibile ma non raccomandata.
      pers = 'rawl dph s1 s2k f2 f3 s3a s3b s4 pr';
      ini  = {'    rawl = fi(zeros(5,1), 1, 21, 13);'
              '    s1 = decode_a1(rawl);'
              ['    [s2k, f2] = decode_a2(s1, ' num2str(N) ');']
              '    f3 = f2;'
              ['    [s3a, s3b] = decode_b1(s2k, ' num2str(N) ');']
              '    s4 = decode_b2(s3a, s3b, f3);'
              '    pr = decode_c1(s4);'
              '    dph = uint8(0);'};
      dec  = {'  if dph == 1'
              '    s1 = decode_a1(rawl); dph = uint8(2);'
              '  elseif dph == 2'
              ['    [s2k, f2] = decode_a2(s1, ' num2str(N) '); dph = uint8(3);']
              '  elseif dph == 3'
              ['    [s3a, s3b] = decode_b1(s2k, ' num2str(N) '); f3 = f2; dph = uint8(4);']
              '  elseif dph == 4'
              '    s4 = decode_b2(s3a, s3b, f3); dph = uint8(5);'
              '  elseif dph == 5'
              '    pr = decode_c1(s4); dph = uint8(6);'
              '  elseif dph == 6'
              '    pv = decode_c2(pr); dph = uint8(0);'
              '  end'
              '  if valid'
              '    rawl(:) = raw; dph = uint8(1);'
              '  end'};
    otherwise
      error('decode_phase_code:decVariant', 'decVariant = fused | p3 | p5 | p6');
  end
end


