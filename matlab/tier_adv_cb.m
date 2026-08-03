function tier_adv_cb(blk)
%TIER_ADV_CB  Callback mask di Donatello_Tier (SOLO visibilita', sicuro su istanza LINKATA).
%  ADV on  -> mostra i 6 slider per-campo (nV..nw), nasconde la tendina NFRAC (irrilevante in ADV).
%  ADV off -> mostra NFRAC (menu discreto 13/8/5/2), nasconde i 6 slider.
%  NON modifica struttura ne' chart: cambia solo Visible dei parametri mask -> ammesso sui link risolti.
  adv = strcmp(get_param(blk,'ADV'),'on');
  mo  = Simulink.Mask.get(blk);
  vis = {'off','on'};                       % vis{adv+1}
  for nm = {'nV','nfat','nacc','naccw','nraw','nw'}
    p = mo.getParameter(nm{1}); if ~isempty(p), p.Visible = vis{adv+1}; end
  end
  pn = mo.getParameter('NFRAC'); if ~isempty(pn), pn.Visible = vis{(~adv)+1}; end
end
