"""
Phase 1 data download — pulls the datasets named in the pre-registration
(see pre_registration.md, Section 1 — currently on branch add-prereg-content /
PR #1, pending review).

- MGSM: HF `juletxara/mgsm`, filtered to en/es/ar/zh -> data/mgsm_<lang>.csv
  (NOTE: 'ar' is not a valid config for this dataset -- confirmed absent,
  see pre_registration.md Amendments Log. Loop below still attempts it and
  reports the failure rather than silently skipping.)
- MAPS: HF `Fujitsu-FRE/MAPS`, a multi-config dataset (not a plain split-only
  load). Pre-registration's "MAPS (GAIA+MATH subsets)" maps to configs
  'Math' and 'GAIA'; 'GAIA-v2-LILT' (the trusted cross-check dataset) turns
  out to live in this same repo as a third config. 'ASB' and 'SWE' configs
  exist in the repo but aren't part of the pre-registered design, so they're
  not pulled here. Each config's splits -> data/maps_<config>_<split>.csv

Prints each dataset's column names after loading so run_phase1.py's
question_col/answer_col can be set to the real field names.
"""

from pathlib import Path

from datasets import load_dataset

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MGSM_LANGS = ["en", "es", "ar", "zh"]
MAPS_CONFIGS = ["Math", "GAIA", "GAIA-v2-LILT"]


def download_mgsm():
    print("\n=== MGSM (juletxara/mgsm) ===")
    for lang in MGSM_LANGS:
        try:
            ds = load_dataset("juletxara/mgsm", lang)
        except Exception as e:
            print(f"[{lang}] FAILED to load: {e}")
            continue

        split = "test" if "test" in ds else list(ds.keys())[0]
        df = ds[split].to_pandas()
        print(f"[{lang}] split={split!r} rows={len(df)} columns={list(df.columns)}")

        out_path = DATA_DIR / f"mgsm_{lang}.csv"
        df.to_csv(out_path, index=False)
        print(f"[{lang}] saved -> {out_path}")


def download_maps():
    print("\n=== MAPS (Fujitsu-FRE/MAPS) ===")
    for config in MAPS_CONFIGS:
        try:
            ds = load_dataset("Fujitsu-FRE/MAPS", config)
        except Exception as e:
            print(f"[{config}] FAILED to load: {e}")
            continue

        for split in ds.keys():
            df = ds[split].to_pandas()
            print(f"[{config}/{split}] rows={len(df)} columns={list(df.columns)}")

            out_path = DATA_DIR / f"maps_{config}_{split}.csv"
            df.to_csv(out_path, index=False)
            print(f"[{config}/{split}] saved -> {out_path}")


if __name__ == "__main__":
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    download_mgsm()
    download_maps()
