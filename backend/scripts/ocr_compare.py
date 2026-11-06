"""
Compare OCR engines side by side on a folder of sample documents.

Usage (from the backend/ folder):

    python scripts/ocr_compare.py --providers gemini,paddle
    python scripts/ocr_compare.py --providers gemini --language ar
    python scripts/ocr_compare.py --list-models        # Gemini models your key can use

Inputs : backend/ocr_samples/*.pdf|png|jpg|jpeg   (git-ignored - real docs OK)
         optional backend/ocr_samples/<name>.truth.txt - the correct text,
         typed by a human; when present we compute character / word error
         rates (lower is better). Without it you still get the raw outputs
         to eyeball.
Outputs: backend/ocr_eval/<name>.<provider>.txt  and  backend/ocr_eval/report.md

Keys are read from backend/.env (GEMINI_API_KEY, GEMINI_MODEL,
AZURE_DI_ENDPOINT, AZURE_DI_KEY). Nothing here touches the database.
"""
import argparse
import os
import re
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import fitz  # noqa: E402
from PIL import Image  # noqa: E402

from app.services.ocr_providers import OCRProviderError, build_provider  # noqa: E402

SAMPLES_DIR = BACKEND_DIR / "ocr_samples"
OUT_DIR = BACKEND_DIR / "ocr_eval"


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    env.update({k: v for k, v in os.environ.items() if k in (
        "GEMINI_API_KEY", "GEMINI_MODEL", "AZURE_DI_ENDPOINT", "AZURE_DI_KEY")})
    return env


def page_images(path: Path, dpi: int = 200) -> list[Image.Image]:
    if path.suffix.lower() == ".pdf":
        images = []
        pdf = fitz.open(str(path))
        for page in pdf:
            pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72))
            images.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
        pdf.close()
        return images
    return [Image.open(path).convert("RGB")]


# --- accuracy metrics --------------------------------------------------------
def _levenshtein(a: list, b: list) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _norm(text: str) -> str:
    text = re.sub(r"^-{2,}\s*Page\s+\d+\s*-{2,}$", "", text, flags=re.I | re.M)
    text = text.replace("‏", "").replace("‎", "")
    return re.sub(r"\s+", " ", text).strip().lower()


def error_rates(hyp: str, truth: str) -> tuple[float, float]:
    h, t = _norm(hyp), _norm(truth)
    cer = _levenshtein(list(h), list(t)) / max(1, len(t))
    wer = _levenshtein(h.split(), t.split()) / max(1, len(t.split()))
    return cer, wer


# --- main --------------------------------------------------------------------
def list_gemini_models(api_key: str) -> None:
    import requests
    r = requests.get("https://generativelanguage.googleapis.com/v1beta/models",
                     headers={"x-goog-api-key": api_key}, timeout=30)
    r.raise_for_status()
    for m in r.json().get("models", []):
        if "generateContent" in m.get("supportedGenerationMethods", []):
            print(m["name"].removeprefix("models/"), "-", m.get("displayName", ""))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--providers", default="gemini", help="comma list: gemini,azure,paddle")
    ap.add_argument("--language", default="en", help="hint passed to the engine: en, ar, ur, auto")
    ap.add_argument("--samples", default=str(SAMPLES_DIR))
    ap.add_argument("--only", default="", help="substring filter on sample file names")
    ap.add_argument("--list-models", action="store_true")
    ap.add_argument("--out", default=str(OUT_DIR), help="output folder (default backend/ocr_eval)")
    args = ap.parse_args()

    env = load_env(BACKEND_DIR / ".env")
    if args.list_models:
        list_gemini_models(env.get("GEMINI_API_KEY", ""))
        return 0

    providers = {}
    for name in [p.strip() for p in args.providers.split(",") if p.strip()]:
        try:
            providers[name] = build_provider(
                name,
                api_key=env.get("GEMINI_API_KEY", "") if name == "gemini" else env.get("AZURE_DI_KEY", ""),
                model=env.get("GEMINI_MODEL") or "gemini-3.6-flash",
                endpoint=env.get("AZURE_DI_ENDPOINT", ""),
            )
        except Exception as e:  # missing key etc.
            print(f"[skip] {name}: {e}")
    if not providers:
        print("No usable providers. Put keys in backend/.env first.")
        return 1

    samples = sorted(p for p in Path(args.samples).iterdir()
                     if p.suffix.lower() in (".pdf", ".png", ".jpg", ".jpeg") and args.only in p.name)
    if not samples:
        print(f"No samples in {args.samples}. Drop PDF/PNG/JPG files there.")
        return 1

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for sample in samples:
        images = page_images(sample)
        truth_file = sample.with_suffix(".truth.txt")
        truth = truth_file.read_text(encoding="utf-8") if truth_file.exists() else None
        for name, provider in providers.items():
            t0 = time.time()
            try:
                pages = provider.extract_pages(images, args.language)
                text = "\n\n".join(f"--- Page {i} ---\n{p}" for i, p in enumerate(pages, 1))
                err = ""
            except OCRProviderError as e:
                text, err = "", str(e)
            secs = time.time() - t0
            (out_dir / f"{sample.stem}.{name}.txt").write_text(text, encoding="utf-8")
            cer = wer = None
            if truth and text:
                cer, wer = error_rates(text, truth)
            rows.append((sample.name, name, len(images), secs, len(text), cer, wer, err))
            status = err or (f"CER {cer:.1%} WER {wer:.1%}" if cer is not None else f"{len(text)} chars")
            print(f"{sample.name:40s} {name:7s} {secs:6.1f}s  {status}")

    lines = ["# OCR comparison", "", f"Language hint: `{args.language}`", "",
             "| sample | engine | pages | seconds | chars | CER | WER | error |",
             "|---|---|---|---|---|---|---|---|"]
    for s, n, pg, secs, chars, cer, wer, err in rows:
        f = lambda v: "" if v is None else f"{v:.1%}"
        lines.append(f"| {s} | {n} | {pg} | {secs:.1f} | {chars} | {f(cer)} | {f(wer)} | {err[:80]} |")
    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nOutputs in {out_dir}  (report.md + one .txt per sample/engine)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
