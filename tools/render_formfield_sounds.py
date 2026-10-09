"""Original Formfield audition sounds. Python standard library; no source samples.

Run: python tools/render_formfield_sounds.py
Writes the five approved product sounds; Passage A is the active transition.
The active-window RMS targets are a starting balance, not a loudness certification.
"""
from array import array
from pathlib import Path
import json
import math
import random
import sys
import wave

ROOT = Path(__file__).resolve().parents[1] / "web" / "frontend" / "public"
RATE = 48000
TAU = 2 * math.pi
SPECS = [
    dict(id="touch", name="Touch", family="Instrument", duration=0.080, rms=-27.0,
         use="Preview · accept", description="A rounded touch. Almost felt before it is heard."),
    dict(id="detent", name="Detent", family="Instrument", duration=0.112, rms=-28.5,
         use="Select · toggle", description="A small mechanism finding its next position."),
    dict(id="transition", name="Passage A", family="Soft sweep", duration=0.180, rms=-32.0,
         file="audio/passage-a-02.wav", use="Page transition · revision 02",
         description="A / Soft sweep. B / Short, dry pass. Both without a pitched tone."),
    dict(id="complete", name="Resolve", family="Glass", duration=0.240, rms=-29.5,
         use="Confirmed completion", description="A clear, steady impression. A result that has settled."),
    dict(id="failure", name="Hold", family="Instrument", duration=0.232, rms=-30.0,
         use="Rejected action", description="A low double touch. A pause, without an alarm."),
    dict(id="transition_b", name="Passage B", family="Dry pass", duration=0.140, rms=-32.0,
         file="audio/passage-b-02.wav", variantOf="transition", use="Page transition · alternative",
         description="A shorter, drier movement with a gentle material edge."),
]


def pulse(t, start, frequency, decay, attack=0.0017, drift=0.0, weight=1.0):
    u = t - start
    if u <= 0:
        return 0.0
    # Exponentially damped mode, with continuous phase during pitch settling.
    phase = TAU * frequency * (u + drift * 0.018 * (1 - math.exp(-u / 0.018)))
    return weight * (1 - math.exp(-u / attack)) * math.exp(-u / decay) * math.sin(phase)


def synth(spec):
    rng = random.Random(20261008 + sum(map(ord, spec["id"])))
    low_noise = 0.0
    noise_lp = noise_smooth = noise_floor = 0.0
    samples = []
    for i in range(round(spec["duration"] * RATE)):
        t = i / RATE
        low_noise += 0.18 * (rng.uniform(-1, 1) - low_noise)
        name = spec["id"]
        if name == "touch":
            value = pulse(t, 0, 390, .013, drift=.20)
            value += pulse(t, 0, 1090, .007, weight=.20)
            value += low_noise * .22 * (1 - math.exp(-t / .0008)) * math.exp(-t / .004)
        elif name == "detent":
            value = pulse(t, 0, 480, .010, weight=.77)
            value += pulse(t, .012, 355, .018, weight=1.0, drift=.09)
            value += pulse(t, .012, 1240, .007, weight=.16)
            value += low_noise * .14 * math.exp(-t / .004) * min(1, t / .001)
        elif name in ("transition", "transition_b"):
            # Aperiodic texture: no oscillators, resonant filters or pitch sweep.
            # Two gentle low-pass stages plus a low-frequency subtraction.
            dry = name == "transition_b"
            cutoff = 1300 if dry else 1050
            alpha = 1 - math.exp(-TAU * cutoff / RATE)
            noise_lp += alpha * (rng.uniform(-1, 1) - noise_lp)
            noise_smooth += alpha * (noise_lp - noise_smooth)
            noise_floor += (1 - math.exp(-TAU * 180 / RATE)) * (noise_smooth - noise_floor)
            u = t / spec["duration"]
            envelope = (1 - math.exp(-t / (.005 if dry else .014))) ** 2
            envelope *= math.exp(-t / (.027 if dry else .047))
            envelope *= (1 - u) ** 1.3
            value = (noise_smooth - noise_floor) * envelope
        elif name == "complete":
            value = pulse(t, 0, 740, .044, attack=.004, weight=.78)
            value += pulse(t, 0, 1191, .038, attack=.006, weight=.16)
            value += pulse(t, 0, 1588, .025, attack=.008, weight=.045)
        else:
            value = pulse(t, 0, 270, .020, attack=.003, drift=.05)
            value += pulse(t, .095, 235, .026, attack=.004, weight=.82)
            value += pulse(t, .095, 613, .014, attack=.003, weight=.12)
        # Both endpoints are exactly silent; a cosine tail prevents hard truncation.
        tail = min(1.0, (spec["duration"] - t - 1 / RATE) / .016)
        value *= .5 - .5 * math.cos(math.pi * max(0.0, tail))
        samples.append(value)
    if spec["id"] in ("transition", "transition_b"):
        window = [math.sin(math.pi * i / (len(samples) - 1)) ** 2 for i in range(len(samples))]
        correction = sum(samples) / sum(window)
        samples = [x - correction * weight for x, weight in zip(samples, window)]
    rms = math.sqrt(sum(x * x for x in samples) / len(samples))
    scale = min(10 ** (spec["rms"] / 20) / rms, .28 / max(map(abs, samples)))
    return [x * scale for x in samples]


def write_wav(name, values):
    integers = array("h", [round(x * 32767) for x in values])
    if sys.byteorder != "little":
        integers.byteswap()
    with wave.open(str(ROOT / "audio" / f"{name}.wav"), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(RATE)
        output.writeframes(integers.tobytes())


def main():
    (ROOT / "audio").mkdir(exist_ok=True)
    for spec in SPECS:
        if spec.get("variantOf"):
            continue
        values = synth(spec)
        file = spec.get("file", f"audio/{spec['id']}.wav")
        write_wav(Path(file).stem, values)
        print(f"{Path(file).name}: {len(values) / RATE * 1000:.0f} ms")


if __name__ == "__main__":
    main()
