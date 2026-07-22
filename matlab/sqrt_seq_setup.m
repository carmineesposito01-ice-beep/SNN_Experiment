function X = sqrt_seq_setup(x) %#codegen
%SQRT_SEQ_SETUP  [IIDM R2] Il radicando come intero senza segno: e' lo stato iniziale della ricorrenza.
%
%  Il trucco che regge tutto: FL_out = FL_in/2 esattamente (4 = 8/2), quindi
%      y_stored = floor(sqrt(x_val) * 2^FL_out) = floor(sqrt(X_stored))
%  cioe' basta la RADICE INTERA dell'intero memorizzato -- nessuna riscalatura.
%
%  `reinterpretcast` e non `double(storedInteger(x))`: e' la stessa operazione sui bit, ma sintetizzabile
%  (un rinominare fili, zero hardware) invece di un passaggio in virgola mobile che HDL Coder rifiuta.
%
%  ⚠️ Presuppone x >= 0, ed e' GARANTITO PER COSTRUZIONE, non sperato: af,bf = cast(max(p,1e-3),..) con
%  troncamento verso zero -> af,bf >= 0 -> x = af*bf >= 0. (Il dominio della prova esaustiva e'
%  esattamente questo: 0 .. 1023,996.)
  X = fi(0, 0, sqrt_seq_nb() * 2, 0);
  X(:) = reinterpretcast(x, numerictype(0, 19, 0));
end
