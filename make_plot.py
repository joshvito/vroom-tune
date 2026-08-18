import pickle, math

ms = pickle.load(open("/tmp/opencode/prv-dsp/measurements.pkl", "rb"))

W, H, M = 900, 420, 50
l, r, t, b = 60, W - M, M, H - M
fmin, fmax = 10, 24000
dbmin, dbmax = -5, 75

def fx(f):
    return l + (math.log10(f) - math.log10(fmin)) / (math.log10(fmax) - math.log10(fmin)) * (r - l)

def fy(db):
    return t + (float(dbmax) - db) / (dbmax - dbmin) * (b - t)

cols = ["#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4"]
out = ["<svg xmlns='http://www.w3.org/2000/svg' width='%d' height='%d'>" % (W, H)]
out.append("<rect width='%d' height='%d' fill='white'/>" % (W, H))

for band in [20, 30, 50, 100, 200, 300, 500, 1000, 2000, 3000, 5000, 10000, 20000]:
    x = fx(band)
    out.append("<line x1='%.1f' y1='%d' x2='%.1f' y2='%d' stroke='#e0e0e0'/>" % (x, t, x, b))
    out.append("<text x='%.1f' y='%d' font-size='10' fill='#888'>%s</text>" % (x, b + 15, band))
for db in range(int(dbmin), int(dbmax + 1), 10):
    y = fy(db)
    out.append("<line x1='%d' y1='%.1f' x2='%d' y2='%.1f' stroke='#e0e0e0'/>" % (l, y, r, y))
    out.append("<text x='%d' y='%.1f' font-size='10' fill='#888'>%d</text>" % (l - 8, y + 3, db))

for i, m in enumerate(ms):
    pts = " ".join("%.1f,%.1f" % (fx(f), fy(s)) for f, s in zip(m["freq"], m["spl"]))
    out.append("<polyline points='%s' fill='none' stroke='%s' stroke-width='1.6'/>" % (pts, cols[i]))

for i, m in enumerate(ms):
    out.append("<circle cx='%.1f' cy='%.1f' r='3' fill='%s'/>" % (fx(400), fy(max(m["spl"])), cols[i]))
    out.append("<text x='%.1f' y='%.1f' font-size='11' fill='%s'>m%d</text>" % (fx(400) + 6, fy(max(m["spl"])), cols[i], i))

out.append("<text x='%d' y='24' font-size='14' fill='#222'>Ford Ranger RTA (1/48 oct, 1216 pts): SPL vs frequency</text>" % M)
out.append("</svg>")
open("/tmp/opencode/prv-dsp/rta_data/plot.svg", "w").write("\n".join(out))
print("plot.svg written")