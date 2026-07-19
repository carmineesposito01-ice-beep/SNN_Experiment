function q = div_seq(num, den) %#codegen
%DIV_SEQ  [IIDM #2] Divisione DIGIT-RECURRENCE (restoring) bit-identica a `fsm_div`, cioe' a
%  `divide(numerictype(T.acc), num, den)` con la fimath di acc_types (RoundingMethod 'Zero').
%
%  FORMA FUNZIONALE (tutta in una chiamata): serve a PROVARE l'ALGORITMO prima di trasformarlo in stato
%  della FSM. I due rischi -- "l'algoritmo e' bit-exact?" e "lo staging e' corretto?" -- sono separati
%  apposta: qui si risponde al primo, con zero chirurgia sulla chart.
%
%  SEMANTICA REPLICATA (spec §5):
%    T.acc = fixdt(1,19,8) = Q10.8. num = N*2^-8, den = D*2^-8 (N,D interi memorizzati a 19 bit)
%    => q_stored = trunc_verso_zero( (N << 8) / D )   -- i 2^-8 si elidono, restano 8 bit sul dividendo.
%  Dividere le MAGNITUDINI e applicare il segno alla fine E' il troncamento verso zero: non e'
%  un'approssimazione della semantica di 'Zero', e' la semantica.
%
%  Gli interi in gioco stanno esattamente in double (dividendo <= 2^26 << 2^53): l'aritmetica qui e'
%  ESATTA, quindi il confronto col riferimento misura l'ALGORITMO, non l'aritmetica dell'host.
  T  = acc_types('fixed');
  nt = numerictype(T.acc);
  WL = nt.WordLength;                 % 19
  FL = nt.FractionLength;             % 8

  N = double(storedInteger(num));
  D = double(storedInteger(den));

  lo = -2^(WL-1);  hi = 2^(WL-1) - 1;   % range degli interi memorizzati di T.acc

  if D == 0
    % Divisione per zero: satura al segno del dividendo (0/0 -> 0). Il cancello su coppie REALI dira'
    % se il riferimento fa lo stesso; non e' un caso che il controllore produca (i denominatori sono
    % guardati a monte da iidm_prep), ma la funzione non deve comunque esplodere.
    if N > 0
      qs = hi;
    elseif N < 0
      qs = lo;
    else
      qs = 0;
    end
  else
    sq = (N < 0) ~= (D < 0);            % segno del quoziente
    A  = abs(N) * 2^FL;                 % dividendo scalato: |N| << FL   (<= 2^18 * 2^8 = 2^26)
    B  = abs(D);                        % divisore magnitudine
    nb = WL + FL;                       % 27 bit di quoziente: copre A/B con B>=1 (A <= 2^26)

    R = 0; Q = 0;
    for i = nb-1:-1:0                   % 1 BIT DI QUOZIENTE PER ITERAZIONE (= per ciclo, in HW)
      abit = mod(floor(A / 2^i), 2);    % bit i-esimo di A
      R = R * 2 + abit;                 % R = (R << 1) | abit
      if R >= B                         % restoring: sottrai solo se ci sta
        R = R - B;
        Q = Q + 2^i;
      end
    end

    if sq, qs = -Q; else, qs = Q; end
    if qs > hi, qs = hi; elseif qs < lo, qs = lo; end   % saturazione al range di T.acc
  end

  q = reinterpretcast(fi(qs, 1, WL, 0), nt);            % ricostruisci il fi dall'intero memorizzato
end
