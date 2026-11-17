"""
A Gemini model that refuses as busy is skipped for a few minutes.

Run from backend/ (needs only requests and Pillow):

    python tests/test_gemini_busy_models.py

Regression test for: an upload took over 3 minutes because every upload
asked three busy models in turn (each answering "high demand" slowly)
before reaching the one that worked. No real API call is made.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.ocr_providers import gemini_provider as gp  # noqa: E402


def check(name: str, ok: bool) -> None:
    print(("PASS  " if ok else "FAIL  ") + name, flush=True)
    if not ok:
        sys.exit(1)


class Resp:
    def __init__(self, status, text="ok"):
        self.status_code = status
        self.text = "busy" if status != 200 else text

    def json(self):
        return {"candidates": [{"content": {"parts": [{"text": "hello"}]}}],
                "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5}}


busy_models = {"model-a", "model-b"}
asked: list[str] = []


def fake_post(url, **kwargs):
    model = url.split("/models/")[-1].split(":")[0]
    asked.append(model)
    return Resp(503 if model in busy_models else 200)


clock = [1000.0]
gp.requests.post = fake_post
gp.time.sleep = lambda seconds: None
gp.time.monotonic = lambda: clock[0]

provider = gp.GeminiProvider("test-key", "model-a", fallback_models=["model-b", "model-c"])

check("first upload still gets an answer", provider._generate([{"text": "x"}], {}) == "hello")
check("it asked the busy models first (one retry each), then the working one",
      asked == ["model-a", "model-a", "model-b", "model-b", "model-c"])

asked.clear()
provider._generate([{"text": "x"}], {})
check("the next upload goes straight to the working model", asked == ["model-c"])

busy_models.clear()
clock[0] += provider.BUSY_COOLDOWN_SECONDS + 1
asked.clear()
provider._generate([{"text": "x"}], {})
check("after the cool-down the main model is asked first again", asked == ["model-a"])

# Every model busy: they are still tried (soonest-available first), not refused outright.
busy_models.update({"model-a", "model-b", "model-c"})
try:
    provider._generate([{"text": "x"}], {})
    check("all busy raises an error", False)
except gp.OCRProviderError:
    check("all busy raises an error (the upload then falls back to the local engine)", True)
busy_models.clear()
asked.clear()
provider._generate([{"text": "x"}], {})
check("when all are cooling down, they are tried anyway and recover", asked == ["model-a"])
asked.clear()
provider._generate([{"text": "x"}], {})
check("a model that answers again loses its busy mark", asked == ["model-a"])

usage = provider.pop_usage()
check("token usage is still collected", usage is not None and usage["input_tokens"] >= 10)
print("All busy-model checks passed.")
