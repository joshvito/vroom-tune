import pickle, csv, os, json, bisect, sys

if len(sys.argv) < 2:
    sys.exit("usage: python export_csv.py <measurements.pkl> [outdir]")
ms_path = sys.argv[1]
outdir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(ms_path) or ".", "rta_data")
os.makedirs(outdir, exist_ok=True)
ms = pickle.load(open(ms_path, "rb"))

for i, m in enumerate(ms):
    start = m["prims"].get("startFreq", 0.0)
    end = m["prims"].get("validEndFreq", m["freq"][-1])
    label = "rta_%d" % i
    with open(os.path.join(outdir, label + ".csv"), "w") as f:
        w = csv.writer(f)
        w.writerow(["freq_hz", "spl_db"])
        for fr, s in zip(m["freq"], m["spl"]):
            w.writerow(["%.4f" % fr, "%.3f" % s])
    # combined JSON
    json.dump(
        {
            "label": m["label"],
            "freq": m["freq"],
            "spl": m["spl"],
            "raw": m["raw"],
            "sampleRate": m["prims"].get("sampleRate"),
        },
        open(os.path.join(outdir, label + ".json"), "w"),
    )

# combined summary CSV, log-spaced octave bands 20..20k
oct_bands = [16, 20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800,
             1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500, 16000, 20000]
with open(os.path.join(outdir, "combined_octave_bands.csv"), "w") as f:
    w = csv.writer(f)
    w.writerow(["band_hz"] + ["m%d_%s" % (i, m["label"].split("PM")[0].split(",")[-1].strip().replace(":", "")) for i, m in enumerate(ms)])
    for b in oct_bands:
        row = []
        for m in ms:
            j = bisect.bisect_left(m["freq"], b)
            row.append("%.1f" % m["spl"][j])
        w.writerow([b] + row)

print("wrote:", os.listdir(outdir))