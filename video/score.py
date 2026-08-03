#!/usr/bin/env python3
"""
Original score for the launch film — synthesized from scratch, so there is
nothing to license and nothing to attribute.

    python3 video/score.py            # -> video/score.wav

Warm editorial ambient in F major, 82 BPM. The arrangement is keyed to the
same scene boundaries as launch.html: it thins out under the cold open, adds a
pulse when the pipeline appears, lifts under the share-card grid, peaks on the
stats, and resolves on the call to action.
"""
import math
import struct
import wave
from pathlib import Path

import numpy as np

SR = 44100
DUR = 64.0
N = int(SR * DUR)
BPM = 82.0
BEAT = 60.0 / BPM          # 0.7317 s
BAR = 4 * BEAT             # 2.927 s

OUT = Path(__file__).resolve().parent / 'score.wav'

# Scene boundaries, mirroring SCENES in launch.html
S_OPEN, S_PROBLEM, S_PIPE, S_HOME, S_EXPL, S_CARDS, S_STATS, S_CTA, S_END = (
    0.0, 6.0, 15.0, 23.6, 32.8, 41.6, 50.4, 56.2, 64.0)

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
music_l = np.zeros(N, dtype=np.float64)   # goes to reverb
music_r = np.zeros(N, dtype=np.float64)
dry_l = np.zeros(N, dtype=np.float64)     # percussion, mostly dry
dry_r = np.zeros(N, dtype=np.float64)


def add(bl, br, sig, t0, pan=0.5, gain=1.0):
    """Mix a mono signal in at t0 with equal-power panning."""
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


# ----------------------------------------------------------------------------
# voices
# ----------------------------------------------------------------------------
def pad(freq, dur, attack=1.4, release=2.2, detune=0.004, bright=0.5):
    """Slow, breathing chord voice: three detuned saw-ish layers, softened."""
    t = t_axis(dur)
    sig = np.zeros_like(t)
    for k, det in enumerate((-detune, 0.0, detune)):
        f = freq * (1 + det)
        # a few harmonics with 1/n rolloff, tilted by `bright`
        for h in (1, 2, 3, 4, 5):
            amp = (1.0 / h ** (2.0 - bright)) * (0.6 if k != 1 else 1.0)
            sig += amp * np.sin(2 * np.pi * f * h * t + k * 1.7 + h * 0.3)
    sig /= 9.0
    # slow vibrato keeps a synth pad from sounding static
    sig *= 1 + 0.02 * np.sin(2 * np.pi * 0.23 * t + freq % 3)

    env = np.ones_like(t)
    a = min(int(attack * SR), len(t))
    r = min(int(release * SR), len(t) - a) if len(t) > a else 0
    env[:a] = np.sin(np.linspace(0, np.pi / 2, a)) ** 2
    if r > 0:
        env[len(t) - r:] = np.cos(np.linspace(0, np.pi / 2, r)) ** 2
    return sig * env


def bell(freq, dur=3.2, decay=1.5, bright=1.0):
    """Struck tone — inharmonic partials, fast attack, long tail."""
    t = t_axis(dur)
    sig = np.zeros_like(t)
    for ratio, amp, dk in ((1.0, 1.0, 1.0), (2.01, 0.42 * bright, 0.62),
                           (3.02, 0.20 * bright, 0.42), (4.98, 0.08 * bright, 0.3)):
        sig += amp * np.sin(2 * np.pi * freq * ratio * t) * np.exp(-t / (decay * dk))
    click = np.exp(-t * 260) * np.sin(2 * np.pi * freq * 6 * t) * 0.15
    return (sig / 1.7 + click) * (1 - np.exp(-t * 900))


def pluck(freq, dur=0.9, decay=0.34):
    """Soft mallet for the arpeggio."""
    t = t_axis(dur)
    sig = (np.sin(2 * np.pi * freq * t)
           + 0.34 * np.sin(2 * np.pi * freq * 2 * t) * np.exp(-t / (decay * 0.5))
           + 0.12 * np.sin(2 * np.pi * freq * 3 * t) * np.exp(-t / (decay * 0.3)))
    return sig * np.exp(-t / decay) * (1 - np.exp(-t * 700)) / 1.4


def kick(dur=0.42):
    """Low heartbeat, not a dance kick."""
    t = t_axis(dur)
    f = 105 * np.exp(-t * 26) + 44
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 8.5)


def tick(dur=0.09, seed=0):
    rng = np.random.default_rng(seed)
    t = t_axis(dur)
    noise = rng.standard_normal(len(t))
    noise = np.diff(noise, prepend=0.0)          # crude high-pass -> airy
    return noise * np.exp(-t * 62)


def riser(dur=1.8, seed=1):
    """Noise swell into a downbeat."""
    rng = np.random.default_rng(seed)
    t = t_axis(dur)
    noise = rng.standard_normal(len(t))
    noise = np.diff(noise, prepend=0.0)
    shape = (t / dur) ** 2.6
    wobble = 1 + 0.3 * np.sin(2 * np.pi * 5 * t * (t / dur))
    return noise * shape * wobble * 0.5


def sub_drop(freq=48.0, dur=2.6):
    t = t_axis(dur)
    return np.sin(2 * np.pi * freq * t) * np.exp(-t * 1.5) * (1 - np.exp(-t * 40))


# ----------------------------------------------------------------------------
# arrangement
# ----------------------------------------------------------------------------
# (start, chord tones low->high, pad gain)
CHORDS = [
    (S_OPEN,      ['F2', 'C3', 'F3', 'A3', 'C4', 'E4'], 0.55),   # Fmaj7  — cold open
    (S_PROBLEM,   ['D2', 'A2', 'D3', 'F3', 'A3', 'C4'], 0.70),   # Dm7    — the problem
    (S_PROBLEM + 3 * BAR, ['Bb2', 'F3', 'Bb3', 'D4', 'F4'], 0.72),  # Bbmaj7
    (S_PIPE,      ['F2', 'C3', 'F3', 'A3', 'C4', 'G4'], 0.80),   # Fmaj9  — pipeline
    (S_PIPE + 3 * BAR, ['C3', 'G3', 'C4', 'E4', 'G4'], 0.80),    # C
    (S_HOME,      ['Bb2', 'F3', 'Bb3', 'D4', 'F4'], 0.78),       # Bbmaj7 — homepage
    (S_HOME + 3 * BAR, ['A2', 'E3', 'A3', 'C4', 'E4'], 0.78),    # Am7
    (S_EXPL,      ['F2', 'C3', 'F3', 'A3', 'C4', 'E4'], 0.78),   # Fmaj7  — explainer
    (S_EXPL + 3 * BAR, ['G2', 'D3', 'G3', 'Bb3', 'D4'], 0.78),   # Gm7
    (S_CARDS,     ['Bb2', 'F3', 'Bb3', 'D4', 'F4', 'A4'], 0.92),  # Bbmaj7 — lift
    (S_CARDS + 3 * BAR, ['C3', 'G3', 'C4', 'E4', 'G4', 'C5'], 0.92),  # C
    (S_STATS,     ['D3', 'A3', 'D4', 'F4', 'A4'], 0.95),         # Dm     — stats
    (S_STATS + 2 * BAR, ['C3', 'G3', 'C4', 'E4', 'G4'], 0.95),   # C
    (S_CTA,       ['F2', 'C3', 'F3', 'A3', 'C4', 'G4'], 0.85),   # Fmaj9  — resolve
]


def build():
    # ---- pads -------------------------------------------------------------
    for idx, (t0, tones, gain) in enumerate(CHORDS):
        nxt = CHORDS[idx + 1][0] if idx + 1 < len(CHORDS) else S_END
        dur = nxt - t0 + 2.6                      # overlap so chords bleed
        bright = 0.42 if t0 < S_PIPE else (0.62 if t0 < S_CARDS else 0.74)
        for vi, name in enumerate(tones):
            pan = 0.5 + (0.22 * math.sin(vi * 1.9 + idx))
            v = pad(hz(name), dur, attack=1.3 if t0 else 2.4,
                    release=2.4, bright=bright)
            add(music_l, music_r, v, t0 - 0.35, pan, 0.115 * gain)

    # ---- opening bell + logo hit -----------------------------------------
    add(music_l, music_r, bell(hz('F4'), 5.0, decay=2.2), 0.55, 0.5, 0.34)
    add(music_l, music_r, bell(hz('C5'), 4.5, decay=1.9), 1.25, 0.42, 0.20)
    add(music_l, music_r, bell(hz('A4'), 4.0, decay=1.7), 2.45, 0.6, 0.15)

    # ---- arpeggio ---------------------------------------------------------
    # eighth notes; density and octave follow the section
    def chord_at(t):
        cur = CHORDS[0]
        for c in CHORDS:
            if c[0] <= t + 1e-6:
                cur = c
        return cur[1]

    step = BEAT / 2
    k = 0
    t = S_PROBLEM
    while t < S_CTA:
        tones = chord_at(t)
        if t < S_PIPE:
            gain, oct_up, skip = 0.185, 0, 2      # sparse under the problem
        elif t < S_HOME:
            gain, oct_up, skip = 0.24, 0, 1
        elif t < S_CARDS:
            gain, oct_up, skip = 0.21, 0, 1
        elif t < S_STATS:
            gain, oct_up, skip = 0.30, 1, 1       # lift: octave up
        else:
            gain, oct_up, skip = 0.32, 1, 1
        if k % skip == 0:
            name = tones[2 + (k // skip) % (len(tones) - 2)]
            f = hz(name) * (2 ** oct_up)
            accent = 1.0 if k % 4 == 0 else (0.62 if k % 2 == 0 else 0.44)
            pan = 0.5 + 0.3 * math.sin(k * 0.8)
            add(music_l, music_r, pluck(f), t, pan, gain * accent)
        k += 1
        t += step

    # ---- pulse ------------------------------------------------------------
    t = S_PIPE
    while t < S_CTA - 0.2:
        beat_in_bar = round(((t - S_PIPE) / BEAT)) % 4
        if beat_in_bar in (0, 2):
            g = 0.19 if t < S_CARDS else 0.25
            if beat_in_bar == 0:
                g *= 1.2
            add(dry_l, dry_r, kick(), t, 0.5, g)
        t += BEAT

    # ---- shaker ticks -----------------------------------------------------
    t, i = S_HOME, 0
    while t < S_STATS + 4 * BEAT:
        g = 0.055 if i % 2 == 0 else 0.030
        add(dry_l, dry_r, tick(seed=i), t, 0.5 + 0.25 * math.sin(i), g)
        i += 1
        t += BEAT / 2

    # ---- transitions ------------------------------------------------------
    for t0, g in ((S_PIPE, 0.14), (S_CARDS, 0.20), (S_CTA, 0.15)):
        add(music_l, music_r, riser(1.8, seed=int(t0)), t0 - 1.8, 0.5, g)
    add(dry_l, dry_r, sub_drop(), S_CARDS, 0.5, 0.24)
    add(dry_l, dry_r, sub_drop(44.0, 3.0), S_CTA, 0.5, 0.20)

    # ---- resolve ----------------------------------------------------------
    add(music_l, music_r, bell(hz('F4'), 6.5, decay=2.6), S_CTA + 0.15, 0.5, 0.30)
    add(music_l, music_r, bell(hz('A4'), 6.0, decay=2.4), S_CTA + 1.35, 0.4, 0.19)
    add(music_l, music_r, bell(hz('C5'), 6.0, decay=2.4), S_CTA + 2.4, 0.62, 0.15)
    add(music_l, music_r, bell(hz('F5'), 7.0, decay=3.0), S_CTA + 3.6, 0.5, 0.13)


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


def reverb(x, room=0.84, damp=0.28):
    combs = (1557, 1617, 1491, 1422, 1277, 1356)
    wet = np.zeros_like(x)
    for d in combs:
        wet += comb(x, d, room)
    wet /= len(combs)
    for d in (225, 556, 441):
        wet = allpass(wet, d, 0.5)
    # one-pole lowpass so the tail stays warm instead of hissy
    a = damp
    out = np.empty_like(wet)
    acc = 0.0
    block = 4096
    for s in range(0, len(wet), block):
        seg = wet[s:s + block]
        # per-sample IIR, done blockwise to stay reasonably quick
        for n in range(len(seg)):
            acc = a * acc + (1 - a) * seg[n]
            out[s + n] = acc
    return out


def main():
    build()

    print('rendering reverb…')
    wet_l = reverb(music_l)
    wet_r = reverb(music_r * 1.0)
    left = music_l * 0.78 + wet_l * 0.34 + dry_l
    right = music_r * 0.78 + wet_r * 0.34 + dry_r

    stereo = np.stack([left, right])

    # trim to a sane working level first, then soft-knee limit, then normalize
    raw_peak = np.abs(stereo).max()
    print(f'  pre-limiter peak {raw_peak:.2f}')
    stereo *= 0.85 / raw_peak
    stereo = np.tanh(stereo * 1.3) / 1.3
    # Leave real headroom: AAC reconstructs inter-sample peaks above the source
    # level, so mastering to ~0.9 here comes back clipping on the other side.
    stereo *= 0.70 / np.abs(stereo).max()

    # fades: up under the cold open, out under the end card
    fi = int(0.5 * SR)
    stereo[:, :fi] *= np.linspace(0, 1, fi) ** 1.5
    fo = int(2.6 * SR)
    stereo[:, -fo:] *= np.cos(np.linspace(0, np.pi / 2, fo)) ** 1.6

    for label, a, b in (('open', 0, 6), ('problem', 6, 15), ('pipeline', 15, 23.6),
                        ('product', 23.6, 41.6), ('cards', 41.6, 50.4),
                        ('stats', 50.4, 56.2), ('cta', 56.2, 64)):
        seg = stereo[:, int(a * SR):int(b * SR)]
        print(f'  {label:9s} rms {np.sqrt((seg ** 2).mean()):.3f}  peak {np.abs(seg).max():.3f}')

    pcm = (np.clip(stereo.T, -1, 1) * 32767).astype('<i2')
    with wave.open(str(OUT), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(f'✓ {OUT}  ({OUT.stat().st_size / 1e6:.1f} MB, {DUR:.0f}s)')


if __name__ == '__main__':
    main()
