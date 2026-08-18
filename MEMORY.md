# Car Audio Tune — Project Memory

## Goal
Extract the REW RTA measurement data from a Ford Ranger audio system and derive
EQ suggestions to match the in-car "Harman" target curve, implemented on a
PRV Audio DSP 2.4X (2-in / 4-out digital processor).

## Data
- Source file: `2020-ford-ranger-rta-measurements-bb.mdat` (324,310 bytes),
  a Java-serialized REW `.mdat`, captured 2026-08-16, 48 kHz.
- 5 RTA captures (moving-microphone method, ~115+ averages, 1/48 octave):
  | # | id        | desc      | RMS  | notes |
  |---|-----------|-----------|------|-------|
  | 0 | baseline  | ambient noise, NO sound playing (noise-floor reference) | 72.7 | not used for EQ |
  | 1 | front left  | FL speaker at driver position | 83.3 | |
  | 2 | rear right  | RR speaker at driver position | 83.2 | |
  | 3 | rear left   | RL speaker at driver position | 81.0 | |
  | 4 | front right | FR speaker at driver position | 82.9 | |
- Each measurement: `isFromRTA=True`, `ppo=96` (points/octave), 1216 points,
  3.66-23640 Hz, freq = startFreq*logStep^i, logStep=2^(1/96). `rawValues == splValues`.
- No EQ was applied when measured (all 28 filter slots = type NONE).
- Baseline (#0) doubles as the noise floor: speaker bands are all >8 dB above it
  (25 Hz tightest at +8.3 dB), so the low end is valid.

## Parser (javastream.py)
Minimal Java ObjectInputStream stream walker. Key REW quirks handled:
- Arrays: `75 <classdesc> [0x70 if TC_REFERENCE] <4-byte len> <data>` (peek logic).
- Enum constant names are TC_STRING (`74 00 04 NONE`), not raw mod-UTF.
- Classdesc superclass can be a TC_REFERENCE (e.g. `71 00 7e 00 4a` -> java.lang.Enum).
- Nested `[[` arrays read as n inner object reads.
- Events tagged with class+field context (`.ctx()`), primitive values captured
  for classes in `Reader.peek`, object-array elements tagged `Name[i]`.

Run: `python javastream.py <file>.mdat` -> out.txt event log.
Extract: `python extract.py` -> measurements.pkl (per-measurement dicts:
prims, spl, raw, filters keyed by index, label, freq grid).
Export: `export_csv.py` -> per-measurement CSV/JSON + octave-band table.
Plot: `make_plot.py` -> rta_data/plot.svg.

## EQ methodology
- Driver-position total = incoherent POWER SUM of the 4 speakers
  (RTA is magnitude-only, no phase): `10*log10(sum 10^(spl/10))`.
- Target (classic in-car Harman / Audiofrog / Andy Wehmeyer):
  +9 dB 20-60 Hz -> taper to 0 by 160 Hz -> flat 160 Hz-3 kHz ->
  gentle rolloff to -6 dB @ 20 kHz.
- EQ(band) = target(b) - total(b) + total(1 kHz). Anchored at 1 kHz.
- DSP 2.4X limits: graphic EQ = 15 bands (input, shared), ISO 2/3-octave
  25/40/63/100/160/250/400/630/1000/1600/2500/4000/6300/10000/16000 Hz,
  +-12 dB. Parametric EQ = 1 per output (freq/gain/Q, +-12 dB, Q 0.4-10).

## Recommended EQ (driver-position power-sum total)
15-band graphic EQ (input): +6.7 @25, +6.1 @40, +4.2 @63, +2.9 @100,
-11.6 @160, -8.6 @250, -5.7 @400, -3.3 @630, 0 @1k, +2.8 @1.6k, +2.9 @2.5k,
-4.8 @4k, -8.8 @6.3k, -8.8 @10k, -5.9 @16k.
Key structure: rear speakers own the 160-250 Hz hump (RR 65.6, RL 61.5,
FR 60.7 vs FL 53.7 @160); fronts own the 4-6.3 kHz peak; all share a
1.6 kHz dip. Baseline was noise, excluded from EQ.

## 4 testable options in dsp24x_eq_suggestions.txt
1. Full (boosts to +6.7 dB).
2. Hybrid: graphic + per-output PEQ (rear 160 Hz -6 dB Q1.5; front 5.6 kHz -5 dB Q2.0).
3. All-cut: shift down 6.7 dB (max boost -> 0), output gain +6.7 dB; some bands
   clamp at -12 (residuals finished with rear 160 -6 / front 8k -4 PEQ).
4. Limited-boost (max +3 dB): shift down 3.7 dB, output gain +3.7 dB; only
   160 Hz residual (-3.3) - close with PEQ 160 -3.5 Q1.5.
   Table 4b per-speaker PEQ (on top of Table 4, residuals after global EQ):
   RR 160 -8 Q1.5 | RL 200 -6 Q1.5 | FR 160 -5 Q1.5 | FL 100 +5 Q1.0 (opt).
   Optional: RL 4k +6 Q1.8, FR 16k -4 Q2.0.

## Files
- `javastream.py` - REW mdat stream walker
- `extract.py` - pulls the 5 measurements into measurements.pkl
- `eq_target.py` - target/EQ math (power sum, Harman target)
- `export_csv.py`, `make_plot.py` - deliverables
- `rta_data/` - per-measurement CSV/JSON, octave bands, plot.svg
- `dsp24x_eq_suggestions.txt` - FINAL DELIVERABLE (all 4 options + per-speaker PEQ)
- `DSP2.4X-Manual-2021.pdf` / `dsp24x.txt` - PRV 2.4X manual (EQ capabilities)
- `measdata_fields.txt` - MeasData 128-field table
- `ois.java`, `oos.java`, `osc.java`, `peek_mdat.py`, `readall_mdat.py`, `manual.txt`, `out.txt` - earlier diagnostics

## Notes / caveats
- Verify after programming: re-measure the 4 speakers at driver position
  (moving mic), power-sum, iterate to +-3 dB of target.
- Bass boost also lifts road/engine rumble (noise is LF-heavy).
- Watch headroom: boosts to +6-7 dB -> limiter ~-6 dB or use option 3/4.
- RTA is magnitude-only: always power-sum, never complex-sum, the speakers.
