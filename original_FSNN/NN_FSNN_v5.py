import torch
import torch.nn as nn
import torch.optim as optim
import torchvision
import torchvision.transforms as transforms
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.colors import Normalize

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"--- AVVIO DEEP SNN V5.1 (ALIF PURE HARDWARE) su {device} ---")


# =====================================================
# 1. FUNZIONI HARDWARE (Spike & Quantizzazione Po2)
# =====================================================
class SurrogateSpike_Hardware(torch.autograd.Function):
    @staticmethod
    def forward(ctx, input_potential, threshold):
        ctx.save_for_backward(input_potential, threshold)
        return (input_potential >= threshold).float()

    @staticmethod
    def backward(ctx, grad_output):
        input_potential, threshold = ctx.saved_tensors
        gamma = 0.3
        spike_pseudo_derivative = 1 / (1 + gamma * torch.abs(input_potential - threshold)) ** 2
        return grad_output * spike_pseudo_derivative, None


spike_fn = SurrogateSpike_Hardware.apply


class PowerOf2Quantize(torch.autograd.Function):
    @staticmethod
    def forward(ctx, weight):
        sign = torch.sign(weight)
        w_abs = torch.abs(weight).clamp(min=1e-5)
        log2_w = torch.clamp(torch.round(torch.log2(w_abs)), min=-4.0, max=1.0)
        # Rilassiamo leggermente la maschera (-5) per far fluire i segnali
        mask = (w_abs > 2 ** (-5)).float()
        return sign * (2.0 ** log2_w) * mask

    @staticmethod
    def backward(ctx, grad_output):
        return grad_output


po2_quantize = PowerOf2Quantize.apply


# =====================================================
# 2. ARCHITETTURA V5.1 ALIF (Adaptive Leaky Integrate & Fire)
# =====================================================
class HiddenLayer_ALIF(nn.Module):
    def __init__(self, in_features, out_features, rank=16, max_delay=3):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.max_delay = max_delay

        self.fc_weight = nn.Parameter(torch.Tensor(out_features, in_features))
        nn.init.xavier_uniform_(self.fc_weight)
        self.register_buffer('delays', torch.randint(0, max_delay, (out_features, in_features)))

        self.rec_U = nn.Parameter(torch.Tensor(out_features, rank))
        self.rec_V = nn.Parameter(torch.Tensor(rank, out_features))
        nn.init.orthogonal_(self.rec_U, gain=0.2)
        nn.init.orthogonal_(self.rec_V, gain=0.2)

        # Omeostasi Locale (Fatica Neurale HW-Friendly)
        self.base_threshold = nn.Parameter(torch.ones(out_features) * 1.5)
        self.thresh_jump = nn.Parameter(torch.ones(out_features) * 0.5)

        self.potential = None
        self.prev_spike = None
        self.fatigue = None
        self.x_buffer = None

    def reset_state(self, batch_size, device):
        self.potential = torch.zeros(batch_size, self.out_features, device=device)
        self.prev_spike = torch.zeros(batch_size, self.out_features, device=device)
        self.fatigue = torch.zeros(batch_size, self.out_features, device=device)
        self.x_buffer = [torch.zeros(batch_size, self.in_features, device=device) for _ in range(self.max_delay)]

    def forward(self, x):
        if self.potential is None: self.reset_state(x.size(0), x.device)

        self.x_buffer.insert(0, x)
        self.x_buffer.pop()

        w_po2 = po2_quantize(self.fc_weight)
        u_po2 = po2_quantize(self.rec_U)
        v_po2 = po2_quantize(self.rec_V)

        current = torch.zeros_like(self.potential)
        for d in range(self.max_delay):
            mask_d = (self.delays == d).float()
            current += torch.nn.functional.linear(self.x_buffer[d], w_po2 * mask_d)

        rec_int = torch.nn.functional.linear(self.prev_spike, v_po2)
        rec_curr = torch.nn.functional.linear(rec_int, u_po2)

        # Leak HW (Bit-Shift >> 3) -> V - V/8
        leak = self.potential / 8.0
        self.potential = self.potential - leak + current + rec_curr

        # La soglia sale in base alla fatica
        eff_thresh = self.base_threshold + torch.relu(self.fatigue)
        spikes = spike_fn(self.potential, eff_thresh)

        # Leak Fatica HW (Bit-Shift >> 4) -> F - F/16
        fatigue_leak = self.fatigue / 8.0
        self.fatigue = self.fatigue - fatigue_leak + (spikes * torch.abs(self.thresh_jump))

        # Soft Reset HW (Sottrazione pura, niente zeri forzati)
        self.potential = self.potential - (spikes * eff_thresh)
        self.prev_spike = spikes
        return spikes


class OutputLayer_LI(nn.Module):
    def __init__(self, in_features, out_features):
        super().__init__()
        self.fc_weight = nn.Parameter(torch.Tensor(out_features, in_features))
        nn.init.xavier_uniform_(self.fc_weight)
        self.potential = None

    def reset_state(self): self.potential = None

    def forward(self, input_spikes):
        if self.potential is None: self.potential = torch.zeros(input_spikes.size(0), self.fc_weight.size(0),
                                                                device=input_spikes.device)
        w_po2 = po2_quantize(self.fc_weight)

        # Prima era: leak = self.potential / 16.0
        # ORA: Il layer decisionale dimentica più in fretta (Shift >> 3)
        leak = self.potential / 8.0

        self.potential = self.potential - leak + torch.nn.functional.linear(input_spikes, w_po2)
        return self.potential


class Deep_SNN_V5_1(nn.Module):
    def __init__(self):
        super().__init__()
        self.layer_hidden = HiddenLayer_ALIF(784, 128, rank=16, max_delay=3)
        self.layer_out = OutputLayer_LI(128, 10)

    def forward_tick(self, x):
        spikes_h = self.layer_hidden(x)
        out = self.layer_out(spikes_h)
        return out, spikes_h


# =====================================================
# 3. ADDESTRAMENTO STABILIZZATO (No Panico da Gradiente)
# =====================================================
transform = transforms.Compose([transforms.ToTensor()])
train_dataset = torchvision.datasets.MNIST(root='./data', train=True, download=True, transform=transform)
test_dataset = torchvision.datasets.MNIST(root='./data', train=False, download=True, transform=transform)
train_loader = torch.utils.data.DataLoader(torch.utils.data.Subset(train_dataset, range(1000)), batch_size=64,
                                           shuffle=True, drop_last=True)

net = Deep_SNN_V5_1().to(device)
criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(net.parameters(), lr=0.005)

print("\nFase 3: Addestramento ALIF...")
for epoch in range(3):
    total_loss = 0
    data_iter = iter(train_loader)
    for _ in range(len(train_loader) // 2):
        images1, labels1 = next(data_iter)
        images2, labels2 = next(data_iter)
        img1_flat, img2_flat = images1.view(64, -1).to(device), images2.view(64, -1).to(device)
        labels1, labels2 = labels1.to(device), labels2.to(device)

        optimizer.zero_grad()
        net.layer_hidden.reset_state(64, device);
        net.layer_out.reset_state()

        loss = 0
        # Fase 1: Immagine 1
        for t in range(10):
            out, _ = net.forward_tick(img1_flat)
            # CALCOLIAMO L'ERRORE SOLO ALL'ULTIMO TICK (Tick 9)! La rete ha tempo di pensare.
            if t == 9: loss += criterion(out, labels1)

        # Fase 2: Immagine 2 (Cambio Scena)
        for t in range(10):
            out, _ = net.forward_tick(img2_flat)
            # ERRORE SOLO ALL'ULTIMO TICK (Tick 9)!
            if t == 9: loss += criterion(out, labels2)

        loss.backward()
        optimizer.step()
        total_loss += loss.item()
    print(f"Epoca {epoch + 1}/3 | Loss Media Sequenziale: {total_loss / (len(train_loader) // 2):.4f}")

# =====================================================
# 4. SIMULAZIONE E LOGGING DEL FLUSSO VIDEO
# =====================================================
print("\nSimulazione Flusso Continuo...")
NUM_FRAMES = 3
TICKS_PER_FRAME = 20
TOTAL_TICKS = NUM_FRAMES * TICKS_PER_FRAME

anim_subset = [test_dataset[i] for i in range(NUM_FRAMES)]
labels_seq = [test_dataset[i][1] for i in range(NUM_FRAMES)]

log_img = np.zeros((TOTAL_TICKS, 784))
log_spikes = np.zeros((TOTAL_TICKS, 128))
log_fatigue = np.zeros((TOTAL_TICKS, 128))
log_out = np.zeros((TOTAL_TICKS, 10))

net.eval()
net.layer_hidden.reset_state(1, device);
net.layer_out.reset_state()

with torch.no_grad():
    for f in range(NUM_FRAMES):
        img_flat = anim_subset[f][0].view(1, -1).to(device)
        for t in range(TICKS_PER_FRAME):
            g_tick = f * TICKS_PER_FRAME + t
            log_img[g_tick] = img_flat.cpu().numpy().flatten()

            out, s_h = net.forward_tick(img_flat)

            log_spikes[g_tick] = s_h.cpu().numpy().flatten()
            log_fatigue[g_tick] = net.layer_hidden.fatigue.cpu().numpy().flatten()
            log_out[g_tick] = out.cpu().numpy().flatten()

# =====================================================
# 5. CRUSCOTTO STATICO (Raster Plot a Bolle Colorate)
# =====================================================
print("Generazione Cruscotto...")
fig_stat = plt.figure(figsize=(18, 10))
gs = fig_stat.add_gridspec(2, 2, width_ratios=[1, 1], height_ratios=[1, 1.5])
ax_raster = fig_stat.add_subplot(gs[0, 0])
ax_fat = fig_stat.add_subplot(gs[0, 1])
ax_out = fig_stat.add_subplot(gs[1, :])

fig_stat.suptitle(f"Deep SNN V5.1 ALIF (FPGA Ready): {labels_seq}", fontsize=18, fontweight='bold')
colors = plt.cm.tab10(np.linspace(0, 1, 10))

for f in range(NUM_FRAMES):
    start_t = f * TICKS_PER_FRAME
    bg = 'lightgray' if f % 2 == 0 else 'white'
    ax_raster.axvspan(start_t, start_t + TICKS_PER_FRAME, color=bg, alpha=0.3)
    ax_fat.axvspan(start_t, start_t + TICKS_PER_FRAME, color=bg, alpha=0.3)
    ax_out.axvspan(start_t, start_t + TICKS_PER_FRAME, color=bg, alpha=0.3)
    if f > 0:
        ax_raster.axvline(x=start_t, color='black', linestyle='--')
        ax_fat.axvline(x=start_t, color='black', linestyle='--')
        ax_out.axvline(x=start_t, color='black', linestyle='--')

# --- RASTER PLOT STILE "BOLLE" ---
t_s, n_s = np.where(log_spikes > 0)
# Estraiamo la fatica esatta di ogni neurone nel momento in cui ha sparato
fatigue_at_spike = log_fatigue[t_s, n_s]

# Calcoliamo una dimensione variabile (da ~40 a ~150) basata sulla fatica
bubble_sizes = 40 + (fatigue_at_spike * 100)

sc_raster = ax_raster.scatter(t_s, n_s, s=bubble_sizes, c=fatigue_at_spike, cmap='cool', edgecolors='black', alpha=0.9)
ax_raster.set_xlim(0, TOTAL_TICKS)
ax_raster.set_ylim(-1, 128)
ax_raster.set_title("Raster Plot: Sparsità Naturale (Colore/Dim = Fatica)")
ax_raster.set_ylabel("ID Neurone")
# Aggiungiamo la barra laterale dei colori
fig_stat.colorbar(sc_raster, ax=ax_raster, label="Livello Fatica Neurale")

# --- FATICA MEDIA GLOBALE ---
mean_fatigue = log_fatigue.mean(axis=1)
ax_fat.plot(range(TOTAL_TICKS), mean_fatigue, color='orange', lw=2.5)
ax_fat.fill_between(range(TOTAL_TICKS), mean_fatigue, color='orange', alpha=0.2)
ax_fat.set_xlim(0, TOTAL_TICKS)
ax_fat.set_title("Fatica Media della Rete (Auto-Regolazione)")
ax_fat.set_ylabel("Innalzamento Soglia Media")

# --- OUTPUT POTENTIALS ---
for i in range(10): ax_out.plot(range(TOTAL_TICKS), log_out[:, i], color=colors[i], lw=3.0, label=f"Classe {i}")
ax_out.set_xlim(0, TOTAL_TICKS)
ax_out.set_title("Potenziale Output (Stabile ed Emergente)")
ax_out.legend(loc='upper right')
ax_out.grid(True)

plt.tight_layout()
plt.show()

# =====================================================
# 6. ANIMAZIONE 3D SINGOLA
# =====================================================
print("Avvio Animazione 3D V5.1...")
N_IN_VIS, N_HID_VIS, N_OUT_VIS = 20, 20, 10
fig_anim, ax_vis = plt.subplots(figsize=(14, 9))
fig_anim.canvas.manager.set_window_title('V5.1 ALIF Topology')

ax_vis.axis('off')
ax_vis.set_xlim(-1.0, 4.0);
ax_vis.set_ylim(-4, max(N_IN_VIS, N_HID_VIS, N_OUT_VIS) + 2)

pos_in = [(0, (N_IN_VIS - 1 - y) + (max(N_IN_VIS, N_HID_VIS, N_OUT_VIS) - N_IN_VIS) / 2) for y in range(N_IN_VIS)]
pos_hid = [(1.5, (N_HID_VIS - 1 - y) + (max(N_IN_VIS, N_HID_VIS, N_OUT_VIS) - N_HID_VIS) / 2) for y in range(N_HID_VIS)]
pos_out = [(3.0, (N_OUT_VIS - 1 - y) + (max(N_IN_VIS, N_HID_VIS, N_OUT_VIS) - N_OUT_VIS) / 2) for y in range(N_OUT_VIS)]

for p1 in pos_in:
    for p2 in pos_hid: ax_vis.plot([p1[0], p2[0]], [p1[1], p2[1]], color='gray', alpha=0.03, lw=0.5)
for p1 in pos_hid:
    for p2 in pos_out: ax_vis.plot([p1[0], p2[0]], [p1[1], p2[1]], color='gray', alpha=0.03, lw=0.5)

scat_in = ax_vis.scatter(*zip(*pos_in), s=150, c='black', edgecolors='white', zorder=5)
scat_hid = ax_vis.scatter(*zip(*pos_hid), s=300, c='black', edgecolors='white', zorder=5)
scat_out = ax_vis.scatter(*zip(*pos_out), s=400, c='black', edgecolors='white', zorder=5)

txt_in = [ax_vis.text(p[0] - 0.2, p[1], '', ha='right', va='center', fontsize=10) for p in pos_in]
txt_hid = [ax_vis.text(p[0] + 0.2, p[1], '', ha='left', va='center', fontsize=10) for p in pos_hid]
txt_out = [ax_vis.text(p[0] + 0.2, p[1], '', ha='left', va='center', fontsize=12, fontweight='bold') for p in pos_out]

dash_fat = ax_vis.text(1.5, max(N_IN_VIS, N_HID_VIS, N_OUT_VIS) + 1.0, '', ha='center', va='center', fontsize=14,
                       fontweight='bold', color='orange',
                       bbox=dict(facecolor='white', edgecolor='orange', boxstyle='round,pad=0.5'))
dashboard = ax_vis.text(1.5, -3.0, '', ha='center', va='center', fontsize=13,
                        bbox=dict(facecolor='black', edgecolor='orange', boxstyle='round,pad=0.8', alpha=0.9),
                        color='white')
time_text = fig_anim.text(0.5, 0.02, '', ha='center', fontsize=15, fontweight='bold',
                          bbox=dict(facecolor='lightgray', alpha=0.8, pad=0.5))

norm_out_v = Normalize(vmin=0, vmax=np.max(log_out) if np.max(log_out) > 0 else 10)
norm_fat = Normalize(vmin=0, vmax=np.max(log_fatigue) if np.max(log_fatigue) > 0 else 1)

anim_state = {'img_idx': -1, 'lat': '-'}


def update(frame):
    img_idx = frame // TICKS_PER_FRAME
    local_tick = frame % TICKS_PER_FRAME
    target = labels_seq[img_idx]

    if img_idx != anim_state['img_idx']:
        anim_state['img_idx'] = img_idx
        anim_state['lat'] = 'Accumulo...'

    img_raw = log_img[frame, :N_IN_VIS]
    hid_spikes = log_spikes[frame, :N_HID_VIS]
    hid_fatigue = log_fatigue[frame, :N_HID_VIS]
    out_v = log_out[frame, :N_OUT_VIS]
    win_idx = np.argmax(out_v)

    scat_in.set_color(plt.cm.Blues(img_raw))
    for i in range(N_IN_VIS): txt_in[i].set_text(f"{img_raw[i]:.1f}")

    colors_hid = []
    for i in range(N_HID_VIS):
        if hid_spikes[i] > 0:
            colors_hid.append('yellow')
        else:
            colors_hid.append(plt.cm.magma(norm_fat(hid_fatigue[i])))
    scat_hid.set_color(colors_hid)

    for i in range(N_HID_VIS):
        if hid_spikes[i] > 0:
            txt_hid[i].set_text(f"🔥 SPIKE"); txt_hid[i].set_color('black')
        else:
            txt_hid[i].set_text(f"f:{hid_fatigue[i]:.1f}"); txt_hid[i].set_color('gray')

    scat_out.set_color(plt.cm.viridis(norm_out_v(out_v)))
    for i in range(N_OUT_VIS):
        txt_out[i].set_text(f"C{i} 🏆 v:{out_v[i]:.1f}" if i == win_idx and out_v[i] > 1.0 else f"C{i} v:{out_v[i]:.1f}")
        txt_out[i].set_color('green' if i == win_idx else 'gray')

    if anim_state['lat'] == 'Accumulo...' and win_idx == target and local_tick > 5: anim_state[
        'lat'] = f"{local_tick} t"

    en_cost = int(np.sum(log_spikes[frame] > 0))
    mean_fat = log_fatigue[frame].mean()

    dash_fat.set_text(f"🟠 FATICA MEDIA (OMEOSTASI): {mean_fat:.2f}")
    dashboard.set_text(
        f"🎯 Target: {target} | ⏱️ Latenza: {anim_state['lat']}\n⚡ Costo (Spike H): {en_cost}\n🛡️ ALIF HW-Aware (Zero Divisioni)")
    time_text.set_text(f"Tick Globale: {frame} | Tick Locale: {local_tick}")

    return scat_in, scat_hid, scat_out, time_text, dashboard, dash_fat, *txt_in, *txt_hid, *txt_out


ani = animation.FuncAnimation(fig_anim, update, frames=TOTAL_TICKS, interval=150, blit=False)
plt.tight_layout()
plt.subplots_adjust(bottom=0.15)
plt.show()