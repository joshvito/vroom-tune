import sys, re, os
from javastream import Reader

if len(sys.argv) < 2:
    sys.exit("usage: python extract.py <input.mdat> [output.pkl]")
path = sys.argv[1]
out_path = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(path)[0] + ".pkl"
r = Reader(open(path, "rb").read())
r.peek = {"roomeqwizard.MeasData", "roomeqwizard.CalData", "roomeqwizard.Filter"}
evs = r.run()

labels = []
raw_meas = []  # list of dicts of all events between top-level MeasData object events

cur = None
active_meas = None
for e in evs:
    k = e[0]
    if k == "string":
        v = e[1]
        if v.startswith("<HTML>"):
            labels.append(v)
        continue
    if k == "object":
        if e[1] == "roomeqwizard.MeasData" and e[2] == "":
            if active_meas is not None:
                raw_meas.append(active_meas)
            active_meas = {"events": []}
        elif active_meas is not None:
            active_meas["events"].append(e)
        continue
    if active_meas is not None and k in ("prim", "arrdata", "arri", "objarray", "enum", "classdesc"):
        active_meas["events"].append(e)

if active_meas is not None:
    raw_meas.append(active_meas)

print("labels:", len(labels), "measurements:", len(raw_meas))

def split_filter_ctx(ctx):
    m = re.search(r"Filter;?\[(\d+)\]", ctx)
    return int(m.group(1)) if m else None

measurements = []
for mi, m in enumerate(raw_meas):
    prims = {}
    spl = None
    raw = None
    freqs = None
    mc_gain = None
    filters = {}
    for e in m["events"]:
        if e[0] == "prim":
            if "Filter;" in e[3]:
                fi = split_filter_ctx(e[3])
                filters.setdefault(fi, {})[e[1]] = e[2]
            else:
                prims[e[1]] = e[2]
        elif e[0] == "arrdata":
            ctx = e[4]
            if ctx.endswith("roomeqwizard.MeasData.splValues"):
                spl = e[3]
            elif ctx.endswith("roomeqwizard.MeasData.rawValues"):
                raw = e[3]
            elif ctx.endswith("roomeqwizard.CalData.gainArray"):
                mc_gain = e[3]
    measurements.append({"prims": prims, "spl": spl, "raw": raw, "mc_gain": mc_gain,
                         "filters": filters, "label": labels[mi] if mi < len(labels) else None})

for i, m in enumerate(measurements):
    p = m["prims"]
    n = len(m["spl"]) if m["spl"] is not None else 0
    start = p.get("startFreq", 0.0)
    logstep = p.get("logStep", 2.0 ** (1.0 / 96.0))
    m["freq"] = [start * (logstep ** j) for j in range(n)]
    times = re.findall(r"\d+:\d+:\d+ [AP]M", m["label"] or "")
    t = times[0] if times else "?"
    print("#%d %s  n=%d  %.1f..%.1f Hz  spl %.1f..%.1f dB  %d filters" % (
        i, t, n, m["freq"][0], m["freq"][-1], m["spl"][0], m["spl"][-1], len(m["filters"])))

import pickle
with open(out_path, "wb") as fh:
    pickle.dump(measurements, fh)
print("wrote", out_path)
