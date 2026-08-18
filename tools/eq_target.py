import pickle, math, bisect, sys

if len(sys.argv) < 2:
    sys.exit("usage: python eq_target.py <measurements.pkl>")
ms = pickle.load(open(sys.argv[1], "rb"))
bands = [25, 40, 63, 100, 160, 250, 400, 630, 1000, 1600, 2500, 4000, 6300, 10000, 16000]
names = ["baseline", "front left", "rear right", "rear left", "front right"]

def interp_spl(m, f):
    fr, s = m["freq"], m["spl"]
    if f <= fr[0]: return s[0]
    if f >= fr[-1]: return s[-1]
    i = bisect.bisect_left(fr, f)
    x = (math.log(f) - math.log(fr[i - 1])) / (math.log(fr[i]) - math.log(fr[i - 1]))
    return s[i - 1] + (s[i] - s[i - 1]) * x

def harman_target(f):
    if f <= 60: return 9.0
    if f <= 160:
        x = (math.log(f) - math.log(60)) / (math.log(160) - math.log(60))
        return 9.0 * (1 - x)
    if f <= 3000: return 0.0
    x = (math.log(f) - math.log(3000)) / (math.log(20000) - math.log(3000))
    return -6.0 * x

# per-speaker SPL at bands
speaker = [[interp_spl(m, b) for b in bands] for m in ms[1:5]]  # FL, RR, RL, FR

# power sum (incoherent) -> total driver-position response
total = [10 * math.log10(sum(10 ** (sp[i] / 10.0) for sp in speaker)) for i in range(15)]
# arithmetic mean for comparison
mean = [sum(sp[i] for sp in speaker) / 4.0 for i in range(15)]
# baseline (m0) if it is the full-system measurement
base = [interp_spl(ms[0], b) for b in bands]

def eq_for(spl):
    i1k = bands.index(1000)
    off = spl[i1k]
    return [round(harman_target(b) - v + off, 1) for b, v in zip(bands, spl)]

print("band     FL    RR    RL    FR  | power total  pwr EQ   | mean total  base(m0)")
for i, b in enumerate(bands):
    pwr = total[i]
    peq = eq_for(total)[i]
    print("%4d   %5.1f %5.1f %5.1f %5.1f | %6.1f   %6.1f  | %6.1f   %6.1f"
          % (b, speaker[0][i], speaker[1][i], speaker[2][i], speaker[3][i],
             pwr, peq, mean[i], base[i]))

peq = eq_for(total)
meq = eq_for(mean)
beq = eq_for(base)
print()
print("power-sum EQ range: %.1f..%.1f  |  mean EQ range: %.1f..%.1f  |  baseline EQ range: %.1f..%.1f"
      % (min(peq), max(peq), min(meq), max(meq), min(beq), max(beq)))
