function [out, valid] = ann_mlp(xn, start) %#codegen
%ANN_MLP  Baseline ANN densa 4->32->32->5 TIME-MULTIPLEXATA (1 MAC/ciclo, 1312 MAC, 1 DSP).
%  Interfaccia come snn_top_b2: [out,valid]=ann_mlp(xn,start). xn Q5.13 (4), out Q7.13 (5).
%  FSM: per ogni layer, per ogni neurone di uscita, accumula sui suoi ingressi (1 MAC/ciclo);
%  ReLU a fine layer (1,2). Pesi da ann_rom (baked). Baseline di POTENZA/AREA, non addestrata.
  W = ann_rom();
  Ta = numerictype(1, 40, 26);                 % accumulatore MAC
  Ty = numerictype(1, 19, 13);                 % attivazioni Q5.13
  To = numerictype(1, 21, 13);                 % uscita Q7.13
  persistent a1 h1 h2 outr layer no ni acc busy
  if isempty(layer)
    a1 = fi(zeros(4,1), Ty); h1 = fi(zeros(32,1), Ty); h2 = fi(zeros(32,1), Ty);
    outr = fi(zeros(5,1), To);
    layer = uint8(0); no = uint8(1); ni = uint8(1); acc = fi(0, Ta); busy = false;
  end
  valid = false;
  out = outr;

  if start && ~busy
    a1 = xn; layer = uint8(1); no = uint8(1); ni = uint8(1); acc = fi(0, Ta); busy = true;
  elseif busy
    % dimensioni del layer corrente
    if layer == uint8(1)
      nin = uint8(4);  nout = uint8(32);
    elseif layer == uint8(2)
      nin = uint8(32); nout = uint8(32);
    else
      nin = uint8(32); nout = uint8(5);
    end
    % un MAC (mult data x data -> DSP48)
    if layer == uint8(1)
      p = fi(W.W1(no, ni) * a1(ni), Ta);
    elseif layer == uint8(2)
      p = fi(W.Wh(no, ni) * h1(ni), Ta);
    else
      p = fi(W.Wo(no, ni) * h2(ni), Ta);
    end
    acc = fi(acc + p, Ta);
    if ni < nin
      ni = ni + uint8(1);
    else
      % fine accumulo per il neurone no: ReLU (layer 1,2) + store
      r = acc;
      if (layer < uint8(3)) && (r < fi(0, Ta))
        r = fi(0, Ta);
      end
      if layer == uint8(1)
        h1(no) = fi(r, Ty);
      elseif layer == uint8(2)
        h2(no) = fi(r, Ty);
      else
        outr(no) = fi(r, To);
      end
      acc = fi(0, Ta); ni = uint8(1);
      if no < nout
        no = no + uint8(1);
      else
        no = uint8(1);
        if layer < uint8(3)
          layer = layer + uint8(1);
        else
          busy = false; valid = true; out = outr;   % inferenza completa
        end
      end
    end
  end
end
