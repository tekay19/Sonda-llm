"""Sohbetler arası kalıcı hafıza: kullanıcı hakkında öğrenilen kalıcı bilgiler."""
import json
import threading
import time
from pathlib import Path

DOSYA = Path(__file__).parent / "veri" / "hafiza.json"
EN_FAZLA = 60
_kilit = threading.Lock()


def yukle():
    try:
        return json.loads(DOSYA.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _yaz(liste):
    DOSYA.parent.mkdir(exist_ok=True)
    DOSYA.write_text(json.dumps(liste[-EN_FAZLA:], ensure_ascii=False, indent=2), encoding="utf-8")


def ekle(bilgiler):
    with _kilit:
        liste = yukle()
        mevcut = {b["metin"].casefold() for b in liste}
        for b in bilgiler:
            b = b.strip()
            if b and b.casefold() not in mevcut:
                liste.append({"id": f"{time.time_ns()}", "metin": b, "zaman": int(time.time())})
                mevcut.add(b.casefold())
        _yaz(liste)


def sil(kimlik=None):
    """kimlik verilmezse tüm hafızayı siler."""
    with _kilit:
        _yaz([] if kimlik is None else [b for b in yukle() if b["id"] != kimlik])


def istem_metni():
    liste = yukle()
    if not liste:
        return ""
    return "KULLANICI HAKKINDA HATIRLADIKLARIN (önceki sohbetlerden):\n" + "\n".join(f"- {b['metin']}" for b in liste)
