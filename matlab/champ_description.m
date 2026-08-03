function d = champ_description(name)
%CHAMP_DESCRIPTION  Testo Description del blocco champion (double, comportamentale). Single-source:
%  lo usa build_library.m (al build) e finalize_descriptions.m (per applicarlo al .slx via set_param,
%  dato che build_library ricrea la libreria da zero e non e' ri-eseguibile sul .slx riordinato).
  L = {
    sprintf('%s - champion SNN car-following, forward ALIF in DOUBLE (riferimento comportamentale).', name)
    ''
    'FUNZIONE: stima i 5 parametri IDM (v0, T, s0, a, b) dallo stato di car-following (s, v, dv, v_l).'
    'E'' il forward del champion in doppia precisione (pesi bakati + normalizzazione + ALIF 10 tick + decode),'
    'self-contained. Serve da RIFERIMENTO: i blocchi HDL (Donatello_LUT/Tier, ACC-IIDM) sono la versione'
    'fixed-point di questo forward.'
    ''
    'SEMANTICA: 1 campione = 1 inferenza (stato ALIF persistente sulla traiettoria). NON e'' HDL-ready: e'''
    'la versione double comportamentale. I/O fisico: s,v,dv,v_l -> v0,T,s0,a,b. Rigenerazione: build_library.m.'
  };
  d = strjoin(L, newline);
end
