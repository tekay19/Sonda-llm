"""Kullanıcı ayarları (veri/ayarlar.json). Dosya bu bilgisayardan çıkmaz, repoya girmez (veri/ .gitignore'da)."""
import json
import os
import threading
from pathlib import Path

DOSYA = Path(__file__).resolve().parent.parent / "veri" / "ayarlar.json"
_kilit = threading.Lock()


def _yukle():
    try:
        veri = json.loads(DOSYA.read_text(encoding="utf-8"))
        return veri if isinstance(veri, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _yaz(veri):
    DOSYA.parent.mkdir(parents=True, exist_ok=True)
    DOSYA.write_text(json.dumps(veri, ensure_ascii=False, indent=1), encoding="utf-8")


def gemini_anahtari():
    """Arayüzden kaydedilen anahtar önceliklidir; yoksa GEMINI_API_KEY."""
    return _yukle().get("gemini_anahtari") or os.environ.get("GEMINI_API_KEY") or None


def gemini_kaydet(anahtar):
    with _kilit:
        veri = _yukle()
        veri["gemini_anahtari"] = anahtar.strip()
        _yaz(veri)


def gemini_sil():
    with _kilit:
        veri = _yukle()
        veri.pop("gemini_anahtari", None)
        _yaz(veri)
