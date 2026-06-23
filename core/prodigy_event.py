"""core/prodigy_event.py — ProdigyEvent: Prodigy adattato a EventProp (EventProp_Study).

PROBLEMA (diagnosticato): Prodigy stima l'adattatore `d` (≈ distanza-dalla-soluzione) dalla
COERENZA del gradiente col progresso accumulato. Il gradiente ESATTO di EventProp è sparso/
discontinuo (eventi + salti agli spike) → poco coerente → la stima di `d` non si accumula →
`d` resta congelato a d0 (lr_eff≈0, niente training). Confermato: Prodigy std → d=1e-6 fisso.

SOLUZIONE (2 meccanismi):
1. **Driver**: alimentare lo stimatore di `d` (e il passo) con il gradiente LISCIATO via EMA
   (bias-corrected) → coerenza ripristinata → `d` si sblocca. VERIFICATO: d 1e-6 → 0.018.
2. **Throttle adattivo della crescita di `d`** (oggettivo, no cap fisso): un cap collasserebbe
   `d` su un LR fisso. Invece si lascia crescere `d` finché il training è STABILE, e si
   CONGELA la crescita quando l'instabilità si accumula. Segnale oggettivo = trend della norma
   del gradiente PRE-clip: rapporto EMA-veloce / EMA-lenta (baseline del regime stabile). Il
   gradiente EventProp è spiky (CV~3) → si usa il TREND, non il singolo step. + gate spike-rate
   (banda sana) come secondo segnale (idea utente: ricerca 2D verso il 'best point' a rate sano).
"""
import math
import torch
from prodigyopt import Prodigy


class ProdigyEvent(Prodigy):
    def __init__(self, params, grad_ema_beta=0.9, rate_gate=None,
                 instab_kappa=2.0, d_max=float('inf'),
                 d_decay=0.9, d_floor=1e-5, probe_up=0.0,
                 loss_aware=False, loss_ema_beta=0.9, po_period=25,
                 po_bad_decay=0.5, po_good_probe=0.0, **kwargs):
        """grad_ema_beta: decay EMA del gradiente per lo stimatore di d (0.9 ~10 step).
        rate_gate: None | (lo, hi) banda spike-rate; fuori banda -> congela crescita di d.
        instab_kappa: soglia del rapporto gn_fast/gn_slow oltre cui si congela d (instabilita
            accumulata). gn_slow = baseline del regime stabile (aggiornata solo quando stabile).
        d_max: cap opzionale su d (default inf = off; preferire il throttle adattivo).
        """
        super().__init__(params, **kwargs)
        self._ge_beta = float(grad_ema_beta)
        self._ge_t = 0
        self._grad_ema = {}              # id(p) -> EMA del gradiente
        self.rate_gate = rate_gate
        self.instab_kappa = float(instab_kappa)
        self.d_max = float(d_max)
        self.d_decay = float(d_decay)    # fattore di decadimento ATTIVO di d sotto instabilita
        self.d_floor = float(d_floor)    # minimo di d (evita collasso a 0)
        self.probe_up = float(probe_up)  # MPPT P&O: perturbazione UP di d se stabile ma stagnante (0=off)
        self._gn_fast = None             # EMA veloce della norma gradiente (trend recente)
        self._gn_slow = None             # EMA lenta = baseline del regime stabile
        # --- Modalita' LOSS-AWARE (P&O bidirezionale sull'obiettivo, peso spike-rate) ---
        # Insight: l'instabilita' di EventProp e' ESPLORAZIONE (salti grandi che atterrano in zone
        # vantaggiose). Non frenare d a caso (un cap uccide l'esplorazione e blocca il training):
        # modula d sul SEGNALE GIUSTO = la loss sta migliorando o peggiorando? loss giu' -> salto
        # produttivo, lascia crescere d; loss su (dopo che d e' cresciuto) -> salto cattivo, decadi d.
        # Spike-rate come PESO (non gate): rate fuori banda raddoppia il decay (doppia conferma).
        self.loss_aware = bool(loss_aware)
        self._lb = float(loss_ema_beta)
        self.po_period = int(po_period)      # step tra due decisioni P&O
        self.po_bad_decay = float(po_bad_decay)   # fattore decay di d su finestra "cattiva"
        self.po_good_probe = float(po_good_probe) # crescita extra di d su finestra "produttiva" (0=off)
        self._loss_ema = None
        self._loss_ref = None
        self._po_t = 0

    @torch.no_grad()
    def step(self, closure=None, spike_rate=None, grad_norm=None, loss=None):
        # 1) EMA del gradiente (bias-corrected) -> coerenza per lo stimatore di d
        self._ge_t += 1
        b = self._ge_beta
        bc = 1.0 - b ** self._ge_t
        for group in self.param_groups:
            for p in group['params']:
                if p.grad is None:
                    continue
                key = id(p)
                ema = self._grad_ema.get(key)
                if ema is None:
                    ema = torch.zeros_like(p.grad)
                    self._grad_ema[key] = ema
                ema.mul_(b).add_(p.grad, alpha=1.0 - b)
                p.grad = ema / bc

        d_before = self.param_groups[0].get('d', None)
        out = super().step(closure)

        if self.loss_aware:
            # === MODALITA' LOSS-AWARE: P&O bidirezionale sull'obiettivo (peso spike-rate) ===
            # Sicurezza per-step: grad inf/nan = salto fatale -> decadi subito (non aspettare la finestra).
            if grad_norm is not None and not math.isfinite(grad_norm):
                for g in self.param_groups:
                    if g.get('d', None) is not None:
                        g['d'] = max(self.d_floor, g['d'] * 0.5)
            elif loss is not None and math.isfinite(float(loss)):
                lval = float(loss)
                if self._loss_ema is None:
                    self._loss_ema = lval; self._loss_ref = lval
                else:
                    self._loss_ema = self._lb * self._loss_ema + (1.0 - self._lb) * lval
                self._po_t += 1
                if self._po_t >= self.po_period:     # decisione P&O ogni po_period step
                    improved = self._loss_ema < self._loss_ref - 1e-6
                    rate_ok = True
                    if self.rate_gate is not None and spike_rate is not None:
                        lo, hi = self.rate_gate
                        rate_ok = (lo <= float(spike_rate) <= hi)
                    if improved and rate_ok:
                        # FINESTRA PRODUTTIVA (loss giu', rate sano): lascia esplorare; probe opzionale
                        if self.po_good_probe > 0.0:
                            for g in self.param_groups:
                                if g.get('d', None) is not None:
                                    g['d'] = min(self.d_max, g['d'] * (1.0 + self.po_good_probe))
                    else:
                        # SALTO CATTIVO (loss su) o rate fuori banda: ritirati -> decadi d.
                        factor = self.po_bad_decay
                        if not rate_ok:
                            factor = factor * self.po_bad_decay   # doppio decay se anche rate malato
                        for g in self.param_groups:
                            if g.get('d', None) is not None:
                                g['d'] = max(self.d_floor, g['d'] * factor)
                    self._loss_ref = self._loss_ema
                    self._po_t = 0
        else:
            # === MODALITA' LEGACY: throttle su trend norma-gradiente + gate spike-rate ===
            throttle = False
            if grad_norm is not None:
                if not math.isfinite(grad_norm):
                    throttle = True                  # inf/nan -> instabile per definizione
                else:
                    if self._gn_fast is None:
                        self._gn_fast = self._gn_slow = grad_norm
                    self._gn_fast = 0.7 * self._gn_fast + 0.3 * grad_norm
                    instab = self._gn_fast / (self._gn_slow + 1e-8)
                    if instab > self.instab_kappa:
                        throttle = True
                    else:
                        self._gn_slow = 0.99 * self._gn_slow + 0.01 * grad_norm
            if self.rate_gate is not None and spike_rate is not None:
                lo, hi = self.rate_gate
                if not (lo <= float(spike_rate) <= hi):
                    throttle = True
            if throttle:
                for g in self.param_groups:
                    if g.get('d', None) is not None:
                        g['d'] = max(self.d_floor, g['d'] * self.d_decay)
            elif self.probe_up > 0.0 and d_before is not None:
                cur = self.param_groups[0].get('d', None)
                if cur is not None and cur <= d_before * (1.0 + 1e-9):
                    for g in self.param_groups:
                        if g.get('d', None) is not None:
                            g['d'] = g['d'] * (1.0 + self.probe_up)

        if self.d_max != float('inf'):               # cap opzionale di sicurezza
            for g in self.param_groups:
                if g.get('d', None) is not None and g['d'] > self.d_max:
                    g['d'] = self.d_max
        return out
