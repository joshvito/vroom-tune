# vroom-tune

Tooling and measurements for tuning car audio systems to a target curve.
Each vehicle gets its own data directory under `vehicles/`; the shared Python
tooling lives in `tools/`.

## Layout

- `tools/` — shared, vehicle-agnostic tooling: REW `.mdat` parser
  (`javastream.py`), extract/export/plot, and EQ math. `reference/` holds REW
  format and Java serialization implementation notes.
- `docs/` — device manuals (PRV DSP 2.4X) and tuning guides.
- `vehicles/<vehicle>/` — one directory per vehicle:
  - `data/REW-data/` — raw REW `.mdat` captures and EQ exports
  - `analysis/` — generated `measurements.pkl`, CSVs, `plot.svg` (gitignored)
  - `dsp24x_eq_suggestions.txt` — EQ deliverables for that vehicle
  - `MEMORY.md` — per-vehicle notes, data summary, and methodology

## Adding a new vehicle

1. `mkdir vehicles/<vehicle>/data/REW-data` and drop in the REW `.mdat` files.
2. From `vehicles/<vehicle>/`, run the shared tooling:

   ```
   python ../../tools/extract.py data/REW-data/<capture>.mdat measurements.pkl
   python ../../tools/export_csv.py measurements.pkl
   python ../../tools/make_plot.py measurements.pkl "My Vehicle RTA"
   python ../../tools/eq_target.py measurements.pkl
   ```

See `vehicles/2020-ford-ranger/MEMORY.md` for the full worked example.
