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

Run (from this vehicle dir, e.g. `vehicles/2020-ford-ranger/`):
- `python ../../tools/javastream.py <file>.mdat` -> out.txt event log
- `python ../../tools/extract.py data/REW-data/<file>.mdat measurements.pkl` ->
  measurements.pkl (per-measurement dicts: prims, spl, raw, filters keyed by
  index, label, freq grid)
- `python ../../tools/export_csv.py measurements.pkl` -> rta_data/ (per-measurement
  CSV/JSON + octave-band table)
- `python ../../tools/make_plot.py measurements.pkl` -> rta_data/plot.svg

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

## Hybrid #2 verification (Aug 18 2026)
Applied option 2 (PEQ rear 160 Hz -6 dB Q1.5 + front 5600 Hz -5 dB Q2.0 +
its graphic EQ table), re-measured each driver + combined front/rear.
Source: `data/REW-data/2020-ford-ranger-rta-measurements-hybrid.mdat`
(388,169 B). Capture order: FR, FL, RR, RL, FR+FL, RR+RL. Extracted to
`analysis/measurements_hybrid.pkl` (6 measurements).
- Residual EQ range improved: -11.6..+6.7 -> -9.4..+2.1 dB.
  25/160/6300 now on target; most bands within +/-3 dB.
- 40/63 Hz OVERCORRECTED (cabin resonance excited by the bass boost):
  four-speaker power sum residual -8.7/-9.4, full-capture (FR+FL & RR+RL)
  residual -10.8/-8.8. ACTION: set graphic EQ 40 Hz -> -4 dB, 63 Hz -> -5 dB;
  keep 25 Hz +6.7. Re-measure and re-verify.
- 160 Hz: full-capture residual +0.5 vs single-driver power sum -4.5 ->
  rear PEQ is working; no further cut (single-driver sums overestimate the
  rear hump in the real combined signal).
- Consistency: FR+FL capture vs FR/FL power sum within ~+/-3 dB; RR+RL runs
  -6.9 dB low @160 and -4.6 dB @400 vs pair sum.
- Front/rear 25 Hz gap in individual captures (rears ~10-17 dB lower) does
  not appear in the full-capture total (-1.0) - fronts carry sub-bass.

## Files
- `../../tools/javastream.py` - REW mdat stream walker (shared)
- `../../tools/extract.py` - pulls measurements out of an mdat into measurements.pkl
- `../../tools/eq_target.py` - target/EQ math (power sum, Harman target)
- `../../tools/export_csv.py`, `../../tools/make_plot.py` - deliverables
- `data/REW-data/` - raw .mdat captures + REW EQ exports
- `analysis/` - measurements.pkl, per-measurement CSV/JSON, octave bands, plot.svg (gitignored)
- `dsp24x_eq_suggestions.txt` - FINAL DELIVERABLE (all 4 options + per-speaker PEQ)
- `../../docs/DSP2.4X-Manual-2021.pdf` / `../../docs/dsp24x.txt` - PRV 2.4X manual (EQ capabilities)
- `../../tools/reference/measdata_fields.txt` - MeasData 128-field table
- `../../tools/reference/ois.java`, `oos.java`, `osc.java`, `../../tools/peek_mdat.py`,
  `../../tools/readall_mdat.py` - earlier diagnostics

## Notes / caveats
- Verify after programming: re-measure the 4 speakers at driver position
  (moving mic), power-sum, iterate to +-3 dB of target.
- Bass boost also lifts road/engine rumble (noise is LF-heavy).
- Watch headroom: boosts to +6-7 dB -> limiter ~-6 dB or use option 3/4.
- RTA is magnitude-only: always power-sum, never complex-sum, the speakers.
