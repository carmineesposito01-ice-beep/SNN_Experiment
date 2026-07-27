function tier_nfrac_round_cb(blk)
%TIER_NFRAC_ROUND_CB  Callback dei 6 slider nfrac per-campo del blocco Donatello_Tier (Modalita' Avanzata):
%  vincola il valore a un INTERO in [1,13]. I bit frazionari (word-length Qm.n) sono numeri NATURALI: un
%  valore come 10.02 non ha senso e romperebbe qz_snn_types_mp (nfrac non-intero). Lo StepSize=1 vincola solo
%  il TRASCINAMENTO dello slider, non il valore DIGITATO: questo callback copre entrambi.
%  Idempotente: se il valore e' gia' intero non chiama set_param -> niente reentrancy (converge in un passo).
  names = {'nV','nfat','nacc','naccw','nraw','nw'};
  for i = 1:numel(names)
    nm = names{i};
    raw = str2double(get_param(blk, nm));
    if isnan(raw), continue; end
    val = min(13, max(1, round(raw)));
    if val ~= raw
      set_param(blk, nm, num2str(val));
    end
  end
end
