"""Sonda sunucusu (FastAPI): arayüz, akış (SSE) uç noktaları, görev komutları."""
import json
from pathlib import Path

import ollama
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import gorev, hafiza
from .asistan import baslik_uret, calistir

STATIK = Path(__file__).resolve().parent.parent / "static"
TERCIH_SIRASI = ["qwen3.6:35b-a3b", "qwen3.8:27b", "qwen2.5:7b"]
ETIKETLER = {
    "qwen3.6:35b-a3b": "Qwen 3.6 · 35B MoE (hızlı)",
    "qwen3.8:27b": "Qwen 3.8 · 27B (en kaliteli, yavaş)",
    "qwen2.5:7b": "Qwen 2.5 · 7B (çok hızlı)",
}

app = FastAPI()
app.mount("/static", StaticFiles(directory=STATIK), name="static")


class Istek(BaseModel):
    soru: str
    gecmis: list[dict] = []
    model: str
    mod: str = "hizli"
    onceki_kaynaklar: list[dict] = []   # son cevabın kaynakları (takip soruları için)
    diger_sohbetler: list[str] = []     # diğer sohbetlerin başlıkları


@app.get("/")
def ana_sayfa():
    return FileResponse(STATIK / "index.html")


@app.get("/api/modeller")
def modeller():
    try:
        kurulu = {m.model for m in ollama.list().models}
    except Exception:
        return []
    return [{"ad": ad, "etiket": ETIKETLER[ad]} for ad in TERCIH_SIRASI if ad in kurulu]


class BaslikIstegi(BaseModel):
    soru: str
    model: str


@app.post("/api/baslik")
def baslik(istek: BaslikIstegi):
    try:
        return {"baslik": baslik_uret(istek.model, istek.soru)}
    except Exception:
        return {"baslik": istek.soru[:60]}


@app.get("/api/hafiza")
def hafiza_listesi():
    return hafiza.yukle()


@app.delete("/api/hafiza/{kimlik}")
def hafiza_sil(kimlik: str):
    hafiza.sil(kimlik)
    return {"tamam": True}


@app.delete("/api/hafiza")
def hafiza_temizle():
    hafiza.sil()
    return {"tamam": True}


@app.get("/api/durum")
def durum():
    try:
        ollama.ps()
        return {"ollama": True}
    except Exception:
        return {"ollama": False}


@app.post("/api/gorev/{gorev_id}/{komut}")
def gorev_komutu(gorev_id: str, komut: str):
    if komut not in ("devam", "durdur"):
        raise HTTPException(400, "komut devam veya durdur olmalı")
    return {"tamam": gorev.komut_ver(gorev_id, komut)}


@app.post("/api/sor")
def sor(istek: Istek):
    gecmis = [{"role": m["role"], "content": m["content"]} for m in istek.gecmis
              if m.get("role") in ("user", "assistant")]

    def olaylar():
        for olay in calistir(istek.soru, gecmis, istek.model, istek.mod,
                             istek.onceki_kaynaklar, istek.diger_sohbetler):
            yield f"data: {json.dumps(olay, ensure_ascii=False)}\n\n"

    return StreamingResponse(olaylar(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})


def main():
    print("Sonda hazır: http://localhost:8765")
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")
