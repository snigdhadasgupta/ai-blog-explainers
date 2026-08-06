#!/usr/bin/env python3
"""
Original score for the launch film — synthesized from scratch, so there is
nothing to license and nothing to attribute.

    python3 video/score.py            # -> video/score.wav

Driving major-key anthem, ~117 BPM. Four-on-the-floor from the moment the
pipeline appears, 16th-note arps, octave bass, claps on 2 and 4, and a
sidechain pump against the kick. The arrangement is keyed to launch.html:
impact on the logo, an accelerating build under the problem statement, the
beat landing with the pipeline, a full drop on the share-card grid, peak on
the stats, and a final hit on the call to action.

The tempo is chosen so the bar grid — anchored at the moment the beat enters
(15.0s) — lands within ~0.15s of the two cuts that matter most: the drop at
41.6s and the end card at 56.2s.
"""
import math
import wave
from pathlib import Path

import numpy as np

SR = 44100

# Must match TIMELINE / RUNTIME in launch.html: the film is authored against
# TIMELINE seconds and played back over RUNTIME. Because BAR is derived from
# the scene boundaries below, compressing the film also raises the tempo.
TIMELINE = 64.0
RUNTIME = 60.0
TS = RUNTIME / TIMELINE

DUR = RUNTIME
N = int(SR * DUR)

OUT = Path(__file__).resolve().parent / 'score.wav'

# Scene boundaries, mirroring SCENES in launch.html
S_OPEN, S_PROBLEM, S_PIPE, S_HOME, S_EXPL, S_CARDS, S_STATS, S_CTA, S_END = (
    x * TS for x in (0.0, 6.0, 15.0, 23.6, 32.8, 41.6, 50.4, 56.2, 64.0))

# Grid anchored where the drums enter, so downbeats hit the cuts that matter.
ANCHOR = S_PIPE
BAR = (S_CTA - S_PIPE) / 20.0      # 2.06 s -> ~116.5 BPM
BEAT = BAR / 4
SIX = BEAT / 4                     # sixteenth

def bar_at(k):
    """Downbeat of bar k, counting from the drum entry (k may be negative)."""
    return ANCHOR + k * BAR


# ----------------------------------------------------------------------------
# pitch
# ----------------------------------------------------------------------------
NAMES = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}


def hz(name: str) -> float:
    """'F3' / 'Bb3' / 'C#5' -> frequency in Hz (A4 = 440)."""
    letter, rest = name[0], name[1:]
    semi = NAMES[letter]
    while rest and rest[0] in 'b#':
        semi += 1 if rest[0] == '#' else -1
        rest = rest[1:]
    midi = 12 * (int(rest) + 1) + semi
    return 440.0 * 2 ** ((midi - 69) / 12)


# ----------------------------------------------------------------------------
# buses
# ----------------------------------------------------------------------------
music_l = np.zeros(N)      # pumped by the kick, sent to reverb
music_r = np.zeros(N)
drum_l = np.zeros(N)       # dry, not ducked
drum_r = np.zeros(N)
kick_times = []


def add(bl, br, sig, t0, pan=0.5, gain=1.0):
    i = int(t0 * SR)
    if i >= N:
        return
    if i < 0:
        sig, i = sig[-i:], 0
    j = min(N, i + len(sig))
    seg = sig[:j - i] * gain
    bl[i:j] += seg * math.cos(pan * math.pi / 2)
    br[i:j] += seg * math.sin(pan * math.pi / 2)


def t_axis(dur):
    return np.arange(int(dur * SR)) / SR


def noise(dur, seed, hp=1):
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(int(dur * SR))
    for _ in range(hp):                     # each diff tilts it brighter
        x = np.diff(x, prepend=0.0)
    return x


# ----------------------------------------------------------------------------
# voices
# ----------------------------------------------------------------------------
def pad(freq, dur, attack=0.4, release=1.2, detune=0.005, bright=0.85):
    """Bright supersaw-ish chord layer."""
    t = t_axis(dur)
    sig = np.zeros_like(t)
    for k, det in enumerate((-detune, 0.0, detune, detune * 2)):
        f = freq * (1 + det)
        for h in (1, 2, 3, 4, 5, 6, 7):
            sig += (1.0 / h ** (2.0 - bright)) * np.sin(2 * np.pi * f * h * t + k * 1.7 + h * .3)
    sig /= 16.0
    env = np.ones_like(t)
    a = min(int(attack * SR), len(t))
    r = min(int(release * SR), len(t) - a) if len(t) > a else 0
    env[:a] = np.linspace(0, 1, a) ** 0.7
    if r > 0:
        env[len(t) - r:] = np.cos(np.linspace(0, np.pi / 2, r)) ** 1.4
    return sig * env


def stab(freq, dur=0.55, decay=0.16):
    """Short chord hit — the brass-ish punch on downbeats."""
    t = t_axis(dur)
    sig = np.zeros_like(t)
    for h in (1, 2, 3, 4, 5, 6):
        sig += (1.0 / h ** 1.15) * np.sin(2 * np.pi * freq * h * t + h)
    return sig / 2.6 * np.exp(-t / decay) * (1 - np.exp(-t * 1400))


def pluck(freq, dur=0.6, decay=0.13):
    """Bright 16th-note arp voice."""
    t = t_axis(dur)
    sig = (np.sin(2 * np.pi * freq * t)
           + 0.5 * np.sin(2 * np.pi * freq * 2 * t) * np.exp(-t / (decay * .6))
           + 0.22 * np.sin(2 * np.pi * freq * 3 * t) * np.exp(-t / (decay * .35))
           + 0.1 * np.sin(2 * np.pi * freq * 4.02 * t) * np.exp(-t / (decay * .25)))
    return sig / 1.6 * np.exp(-t / decay) * (1 - np.exp(-t * 2200))


def bass(freq, dur, decay=0.22):
    """Driving octave bass with a filter-ish brightness decay."""
    t = t_axis(dur)
    sig = np.zeros_like(t)
    for h in (1, 2, 3, 4, 5):
        sig += (1.0 / h) * np.sin(2 * np.pi * freq * h * t) * np.exp(-t / (decay / (h * .45)))
    body = np.sin(2 * np.pi * freq * t) * np.exp(-t / (decay * 1.9))
    return (sig / 2.2 + body * 0.34) * (1 - np.exp(-t * 900))


def kick(dur=0.52, weight=1.0):
    """Heavy kick: long pitch sweep, a sub tail under it, and a hard beater."""
    t = t_axis(dur)
    f = 168 * np.exp(-t * 38) + 41
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7.6)
    sub = np.sin(2 * np.pi * 43 * t + 0.4) * np.exp(-t * 6.2) * 0.34 * weight
    beater = noise(dur, 7, hp=2)[:len(t)] * np.exp(-t * 300) * 0.42
    punch = np.sin(2 * np.pi * 128 * t) * np.exp(-t * 46) * 0.5
    x = body + sub + beater + punch
    return np.tanh(x * 1.5) / 1.5           # saturation = more apparent weight


def clap(seed=3):
    """Three quick noise bursts plus a short tail."""
    dur = 0.34
    t = t_axis(dur)
    out = np.zeros_like(t)
    for off, amp in ((0.0, 1.0), (0.011, 0.85), (0.023, 0.7)):
        i = int(off * SR)
        seg = noise(dur - off, seed + int(off * 1000), hp=2)
        out[i:i + len(seg)] += amp * seg * np.exp(-t_axis(dur - off) * 130)
    out += noise(dur, seed + 9, hp=2) * np.exp(-t * 26) * 0.32
    return out * 0.5


def hat(open_=False, seed=5):
    dur = 0.26 if open_ else 0.075
    t = t_axis(dur)
    return noise(dur, seed, hp=2) * np.exp(-t * (13 if open_ else 78)) * 0.5


def crash(seed=11):
    dur = 2.4
    t = t_axis(dur)
    return noise(dur, seed, hp=1) * np.exp(-t * 2.1) * (1 - np.exp(-t * 900)) * 0.4


def riser(dur, seed=1, tone=True):
    """Noise sweep, optionally with a pitch riser under it."""
    t = t_axis(dur)
    x = noise(dur, seed, hp=2) * (t / dur) ** 2.2
    if tone:
        f = 180 * 2 ** (2.6 * (t / dur))
        x += np.sin(2 * np.pi * np.cumsum(f) / SR) * (t / dur) ** 3.4 * 0.5
    return x * 0.5


def impact(seed=21):
    """Downbeat boom for section starts."""
    dur = 2.0
    t = t_axis(dur)
    sweep = np.sin(2 * np.pi * np.cumsum(70 * np.exp(-t * 5) + 38) / SR) * np.exp(-t * 3.0)
    return sweep + noise(dur, seed, hp=1) * np.exp(-t * 9) * 0.35


# ----------------------------------------------------------------------------
# harmony — major-key only, voiced high and open
# ----------------------------------------------------------------------------
CH = {
    'F':    (['F2', 'F3'], ['F3', 'A3', 'C4', 'F4', 'A4'], ['F4', 'A4', 'C5', 'F5']),
    'Bb':   (['Bb2', 'Bb3'], ['Bb3', 'D4', 'F4', 'Bb4', 'D5'], ['Bb4', 'D5', 'F5', 'Bb5']),
    'C':    (['C3', 'C4'], ['C4', 'E4', 'G4', 'C5', 'E5'], ['C5', 'E5', 'G5', 'C6']),
    'Dm':   (['D3', 'D4'], ['D4', 'F4', 'A4', 'D5', 'F5'], ['D5', 'F5', 'A5', 'D6']),
    'Csus': (['C3', 'C4'], ['C4', 'F4', 'G4', 'C5', 'F5'], ['C5', 'F5', 'G5', 'C6']),
}

# (bar index from the drum entry, chord) — two bars each
PROG = [
    (-4, 'Bb'), (-2, 'C'),                                  # build
    (0, 'F'), (2, 'C'), (4, 'Bb'), (6, 'F'),                # pipeline / homepage
    (8, 'Bb'), (10, 'F'), (12, 'C'),                        # explainer
    (13, 'Bb'), (15, 'C'), (17, 'F'), (19, 'Csus'),         # drop + stats
    (20, 'F'), (22, 'Bb'), (24, 'F'),                       # end card
]


def chord_at(t):
    cur = PROG[0]
    for p in PROG:
        if bar_at(p[0]) <= t + 1e-6:
            cur = p
    return CH[cur[1]]


def build():
    # ---- pads / chord bed -------------------------------------------------
    for i, (bk, name) in enumerate(PROG):
        t0 = bar_at(bk)
        t1 = bar_at(PROG[i + 1][0]) if i + 1 < len(PROG) else S_END
        if t1 <= 0:
            continue
        tones = CH[name][1]
        gain = 0.55 if t0 < S_PIPE else (0.8 if t0 < S_CARDS else 1.0)
        for vi, nm in enumerate(tones):
            pan = 0.5 + 0.26 * math.sin(vi * 2.1 + i)
            add(music_l, music_r, pad(hz(nm), t1 - t0 + 0.9), t0, pan, 0.105 * gain)

    # ---- cold open: impact + swell ---------------------------------------
    add(drum_l, drum_r, impact(), 0.5, 0.5, 0.80)
    add(music_l, music_r, crash(), 0.5, 0.5, 0.44)
    for nm, t0, g in (('F3', 0.55, .30), ('F4', 0.55, .46), ('C5', 0.55, .34), ('A4', 0.55, .28),
                      ('F5', 2.6, .26), ('C5', 3.6, .20), ('F5', 4.6, .18)):
        add(music_l, music_r, stab(hz(nm), 2.4, decay=0.9), t0, 0.5, g)
    # ---- build under the problem statement --------------------------------
    # sixteenth pluck pattern, thinning up into the drop
    t, i = S_PROBLEM, 0
    while t < S_PIPE:
        tones = chord_at(t)[2]
        dens = (t - S_PROBLEM) / (S_PIPE - S_PROBLEM)       # 0 -> 1
        if i % 2 == 0 or dens > 0.45:
            g = 0.17 + 0.20 * dens
            add(music_l, music_r, pluck(hz(tones[i % len(tones)])), t,
                0.5 + 0.3 * math.sin(i * .9), g)
        i += 1
        t += SIX * 2
    add(music_l, music_r, riser(3.4, seed=2), S_PIPE - 3.4, 0.5, 0.34)
    add(music_l, music_r, riser(2.32, seed=4), S_CARDS - 2.6, 0.5, 0.40)
    add(music_l, music_r, riser(1.9, seed=6, tone=False), S_STATS - 1.9, 0.5, 0.22)

    # ---- the groove -------------------------------------------------------
    # The beat runs from the logo hit to the end card — the film opens and
    # closes hot, and the sections differentiate by density, not by silence.
    DRUM_IN = bar_at(-7)          # ~0.6 s, right under the opening impact
    DRUM_OUT = bar_at(23)         # ~62.4 s, final hit rings over the fade
    # Everything cuts out for half a beat before the drop, so it lands harder.
    GAP = (S_CARDS - 0.55 * BEAT, S_CARDS - 0.01)

    def in_gap(t):
        return GAP[0] <= t < GAP[1]

    def section_gain(t):
        if t < S_PROBLEM:
            return 0.66          # cold open: driving, but the logo still reads
        if t < S_PIPE:
            return 0.80          # build
        if t < S_HOME:
            return 0.95
        if t < S_EXPL:
            return 0.84          # ease off under the first product shot
        if t < S_CARDS:
            return 0.92
        return 1.0               # drop, stats, end card

    # kick: four on the floor, all the way through
    t = DRUM_IN
    while t < DRUM_OUT:
        if not in_gap(t):
            g = 0.80 * (0.86 if t < S_PIPE else 1.0) * (1.0 if t < S_CARDS else 1.28)
            add(drum_l, drum_r, kick(weight=1.0 if t < S_CARDS else 1.25), t, 0.5, g)
            kick_times.append(t)
        t += BEAT

    # claps on 2 and 4; doubled onto the offbeats once the drop lands
    t = bar_at(-6) + BEAT
    while t < DRUM_OUT:
        if not in_gap(t):
            add(drum_l, drum_r, clap(), t, 0.5, 0.46 * section_gain(t))
        if t >= S_CARDS and not in_gap(t + BEAT):
            add(drum_l, drum_r, clap(seed=17), t + BEAT, 0.5, 0.16)
        t += 2 * BEAT

    # hats: eighths, open on the offbeat once the drop lands
    t, i = DRUM_IN, 0
    while t < DRUM_OUT:
        op = t >= S_CARDS and i % 4 == 2
        if not in_gap(t):
            add(drum_l, drum_r, hat(op, seed=50 + i % 7), t,
                0.5 + 0.2 * math.sin(i), (0.17 if op else 0.10) * section_gain(t))
        i += 1
        t += BEAT / 2

    # bass: driving eighths with octave jumps, sixteenth pickups after the drop
    t, i = bar_at(-4), 0
    while t < DRUM_OUT:
        roots = chord_at(t)[0]
        f = hz(roots[1] if i % 4 == 3 else roots[0])
        if not in_gap(t):
            g = (0.26 if t < S_CARDS else 0.33) * section_gain(t)
            add(music_l, music_r, bass(f, BEAT), t, 0.5, g)
            if t >= S_CARDS and i % 2 == 1:
                add(music_l, music_r, bass(hz(roots[1]), BEAT / 2, decay=0.12),
                    t + BEAT / 4, 0.5, g * 0.5)
        i += 1
        t += BEAT / 2

    # arp: sixteenths, octave up after the drop
    t, i = S_PIPE, 0
    while t < DRUM_OUT:
        tones = chord_at(t)[2 if t >= S_CARDS else 1]
        f = hz(tones[i % len(tones)])
        accent = 1.0 if i % 4 == 0 else (0.6 if i % 2 == 0 else 0.45)
        g = (0.26 if t < S_CARDS else 0.38) * accent * section_gain(t)
        if not in_gap(t):
            add(music_l, music_r, pluck(f), t, 0.5 + 0.32 * math.sin(i * .7), g)
        i += 1
        t += SIX

    # chord stabs: downbeats, then every beat through the drop and stats
    k = -7
    while bar_at(k) < S_END:
        t0 = bar_at(k)
        tones = chord_at(t0)[1]
        hits = [0.0] if t0 < S_CARDS else [0.0, 2 * BEAT, 3.5 * BEAT]
        for off in hits:
            th = t0 + off
            if th < DRUM_IN or th >= DRUM_OUT or in_gap(th):
                continue
            g = (0.17 if th < S_PIPE else 0.20) if th < S_CARDS else 0.30
            if off:
                g *= 0.7
            for nm in tones:
                add(music_l, music_r, stab(hz(nm)), th, 0.5, g)
        k += 1

    # rolls into the two biggest moments
    for target, n, g0 in ((S_PIPE, 4, 0.10), (S_CARDS, 6, 0.14)):
        t, i = target - 4 * BEAT, 0
        while t < target - 0.02:
            step = BEAT / (2 if i < 4 else (3 if i < 9 else 4))
            frac = (t - (target - 4 * BEAT)) / (4 * BEAT)
            if not in_gap(t):
                add(drum_l, drum_r, clap(seed=70 + i), t, 0.5, g0 + 0.30 * frac)
            i += 1
            t += step
        if i > n:                       # reverse-crash suck into the downbeat
            end = GAP[0] if target == S_CARDS else target
            add(music_l, music_r, np.flip(crash(seed=int(target))), end - 2.4, 0.5, 0.26)

    # ---- section markers --------------------------------------------------
    for t0, g in ((S_OPEN + 0.5, .34), (S_PIPE, .32), (S_HOME, .18), (S_EXPL, .18),
                  (S_CARDS, .58), (S_STATS, .32), (S_CTA, .46)):
        add(drum_l, drum_r, crash(seed=int(t0) + 11), t0, 0.5, g)
    add(drum_l, drum_r, impact(seed=31), S_CARDS, 0.5, 0.72)
    add(drum_l, drum_r, impact(seed=33), S_CTA, 0.5, 0.56)
    # final hit — lands on the last downbeat and rings out over the fade
    add(drum_l, drum_r, crash(seed=77), DRUM_OUT, 0.5, 0.52)
    add(drum_l, drum_r, impact(seed=79), DRUM_OUT, 0.5, 0.62)
    for nm in CH['F'][1] + ['F5', 'C6']:
        add(music_l, music_r, stab(hz(nm), 2.4, decay=0.9), DRUM_OUT, 0.5, 0.16)

    # ---- end card: last hit, then let it ring -----------------------------
    for nm in CH['F'][1] + ['F5', 'C6']:
        add(music_l, music_r, pad(hz(nm), 7.0, attack=0.05, release=4.5), S_CTA, 0.5, 0.055)
    for nm, off, g in (('F5', 0.0, .26), ('C6', 0.9, .17), ('A5', 1.7, .13)):
        add(music_l, music_r, stab(hz(nm), 3.0, decay=1.1), S_CTA + off, 0.5, g)


# ----------------------------------------------------------------------------
# reverb (Schroeder: parallel combs -> series allpass)
# ----------------------------------------------------------------------------
def comb(x, delay, gain):
    y = x.copy()
    for i in range(delay, len(y), delay):
        j = min(i + delay, len(y))
        y[i:j] += gain * y[i - delay:i - delay + (j - i)]
    return y


def allpass(x, delay, gain=0.5):
    y = comb(x, delay, -gain)
    out = np.zeros_like(y)
    out[delay:] = y[:-delay]
    return out + gain * y


def onepole_lp(x, a):
    """One-pole lowpass via FFT convolution with a truncated exponential."""
    k = int(min(len(x), max(64, 8 / (1 - a))))
    imp = (1 - a) * a ** np.arange(k)
    n = 1 << (len(x) + k - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, n) * np.fft.rfft(imp, n), n)[:len(x)]
    return y


def true_peak(x, os=4, chunk=1 << 17, ov=2048):
    """Inter-sample (true) peak, via 4x oversampling. Sample peak alone
    under-reads what a lossy decoder will reconstruct."""
    pk = 0.0
    for i in range(0, len(x), chunk):
        seg = x[max(0, i - ov):i + chunk + ov]
        if len(seg) < 16:
            continue
        up = np.fft.irfft(np.fft.rfft(seg), len(seg) * os) * os
        pk = max(pk, np.abs(up).max())
    return pk

def reverb(x, room=0.78, damp=0.42):
    wet = np.zeros_like(x)
    for d in (1557, 1617, 1491, 1422, 1277, 1356):
        wet += comb(x, d, room)
    wet /= 6.0
    for d in (225, 556, 441):
        wet = allpass(wet, d, 0.5)
    return onepole_lp(wet, damp)


def sidechain():
    """Classic pump: duck the music bus on every kick."""
    env = np.ones(N)
    t = t_axis(0.34)
    shape = 1 - 0.56 * np.exp(-t / 0.095)
    for tk in kick_times:
        i = int(tk * SR)
        j = min(N, i + len(shape))
        env[i:j] = np.minimum(env[i:j], shape[:j - i])
    return onepole_lp(env, 0.55)


def main():
    build()

    duck = sidechain()
    ml, mr = music_l * duck, music_r * duck

    print('rendering reverb…')
    left = ml * 0.86 + reverb(ml) * 0.22 + drum_l
    right = mr * 0.86 + reverb(mr) * 0.22 + drum_r

    stereo = np.stack([left, right])
    raw = np.abs(stereo).max()
    print(f'  pre-limiter peak {raw:.2f}')
    stereo *= 0.95 / raw
    # Roll off the extreme top before limiting: the diff()-tilted noise sources
    # pile energy at 15-20 kHz, which is exactly where AAC overshoots worst.
    for ch in (0, 1):
        stereo[ch] = onepole_lp(onepole_lp(stereo[ch], 0.157), 0.157)
    stereo *= 0.95 / np.abs(stereo).max()
    stereo = np.tanh(stereo * 2.1) / 2.1            # drives the mix harder = louder
    # AAC reconstructs inter-sample peaks well above the source on dense,
    # brickwalled material — mastering above ~0.62 here comes back clipping.
    tp = max(true_peak(stereo[0]), true_peak(stereo[1]))
    print(f'  true peak before master {tp:.2f} (sample peak {np.abs(stereo).max():.2f})')
    stereo *= 0.80 / tp

    fi = int(0.35 * SR)
    stereo[:, :fi] *= np.linspace(0, 1, fi) ** 1.5
    fo = int(1.3 * SR)          # short — the last hit rings, it does not drift out
    stereo[:, -fo:] *= np.cos(np.linspace(0, np.pi / 2, fo)) ** 1.4

    for label, a, b in (('open', S_OPEN, S_PROBLEM), ('build', S_PROBLEM, S_PIPE),
                        ('beat in', S_PIPE, S_HOME), ('product', S_HOME, S_CARDS),
                        ('DROP', S_CARDS, S_STATS), ('stats', S_STATS, S_CTA),
                        ('end card', S_CTA, S_END)):
        seg = stereo[:, int(a * SR):int(b * SR)]
        rms = np.sqrt((seg ** 2).mean())
        print(f'  {label:9s} rms {rms:.3f} {"#" * int(rms * 150)}')

    pcm = (np.clip(stereo.T, -1, 1) * 32767).astype('<i2')
    with wave.open(str(OUT), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(f'✓ {OUT}  ({OUT.stat().st_size / 1e6:.1f} MB, {DUR:.0f}s, '
          f'{240 / BAR:.1f} BPM, {len(kick_times)} kicks)')


if __name__ == '__main__':
    main()
