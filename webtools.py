"""Web araçları: çok motorlu arama, yeniden sıralama, paralel sayfa okuma (HTML + PDF)."""
import io
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, urlunparse

import httpx
import numpy as np
import ollama
import trafilatura
from ddgs import DDGS
from pypdf import PdfReader

EMBED_MODEL = "bge-m3"
METIN_MOTORLARI = ["duckduckgo", "bing", "brave"]
HABER_MOTORLARI = ["duckduckgo", "bing", "yahoo"]
SITE_BASINA_EN_FAZLA = 2
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0 Safari/537.36")
_sayfa_onbellegi = {}


def alan_adi(url):
    return urlparse(url).netloc.lower().removeprefix("www.")


def _normal_url(url):
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc.lower().removeprefix("www."), p.path.rstrip("/"), "", p.query, ""))


def embed(metinler):
    # CPU'da çalıştır: GPU'yu ana modele bırakır, onu bellekten attırmaz
    v = np.array(ollama.embed(model=EMBED_MODEL, input=metinler, options={"num_gpu": 0})["embeddings"])
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def _tek_motor(sorgu, motor, haber, adet):
    try:
        with DDGS() as d:
            if haber:
                return [{"baslik": r["title"], "url": r["url"], "ozet": r.get("body", ""),
                         "tarih": (r.get("date") or "")[:10]}
                        for r in d.news(sorgu, region="tr-tr", max_results=adet, backend=motor)]
            return [{"baslik": r["title"], "url": r["href"], "ozet": r.get("body", "")}
                    for r in d.text(sorgu, region="tr-tr", max_results=adet, backend=motor)]
    except Exception:
        return []


def web_ara(sorgular, soru=None, adet=10, haber=False):
    """Tüm sorguları tüm motorlarda paralel arar, sonuçları birleştirip sıralar.

    Sıralama: motorlar arası RRF (çok motorda çıkan öne geçer) + soruyla anlamsal benzerlik.
    Aynı siteden en fazla SITE_BASINA_EN_FAZLA sonuç döner.
    """
    if isinstance(sorgular, str):
        sorgular = [sorgular]
    motorlar = HABER_MOTORLARI if haber else METIN_MOTORLARI
    isler = [(s, m) for s in sorgular for m in motorlar]
    with ThreadPoolExecutor(max_workers=len(isler)) as havuz:
        listeler = list(havuz.map(lambda i: _tek_motor(i[0], i[1], haber, 10), isler))

    birlesik, rrf = {}, {}
    for liste in listeler:
        for sira, r in enumerate(liste):
            if not r["url"].startswith("http"):
                continue
            anahtar = _normal_url(r["url"])
            onceki = birlesik.get(anahtar)
            if not onceki or len(r["ozet"]) > len(onceki["ozet"]):
                birlesik[anahtar] = r
            rrf[anahtar] = rrf.get(anahtar, 0) + 1 / (20 + sira)
    if not birlesik:
        return []

    anahtarlar = list(birlesik)
    puan = np.array([rrf[a] for a in anahtarlar])
    puan = puan / puan.max()
    try:
        v = embed([soru or sorgular[0]] + [f"{birlesik[a]['baslik']}. {birlesik[a]['ozet']}" for a in anahtarlar])
        puan = 0.5 * puan + 0.5 * (v[1:] @ v[0])
    except Exception:
        pass

    sonuc, site_sayisi = [], {}
    for i in np.argsort(-puan):
        r = birlesik[anahtarlar[i]]
        alan = alan_adi(r["url"])
        if site_sayisi.get(alan, 0) >= SITE_BASINA_EN_FAZLA:
            continue
        site_sayisi[alan] = site_sayisi.get(alan, 0) + 1
        sonuc.append(r)
        if len(sonuc) >= adet:
            break
    return sonuc


def _pdf_metni(icerik):
    okuyucu = PdfReader(io.BytesIO(icerik))
    return "\n".join((s.extract_text() or "") for s in okuyucu.pages[:40])


def sayfa_getir(url):
    """Sayfanın ana metnini çıkarır (reklam, menü vb. atılır). PDF'leri de okur."""
    if url in _sayfa_onbellegi:
        return _sayfa_onbellegi[url]
    baslik = alan_adi(url)
    try:
        yanit = httpx.get(url, timeout=15, follow_redirects=True, headers={
            "User-Agent": UA, "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8"})
        yanit.raise_for_status()
        tur = yanit.headers.get("content-type", "")
        if "pdf" in tur or url.lower().endswith(".pdf"):
            metin = _pdf_metni(yanit.content)
            baslik = url.rsplit("/", 1)[-1] or baslik
        else:
            metin = trafilatura.extract(yanit.text, include_tables=True, favor_recall=True) or ""
            eslesme = re.search(r"<title[^>]*>(.*?)</title>", yanit.text, re.S | re.I)
            if eslesme:
                baslik = " ".join(eslesme.group(1).split())[:150]
    except Exception as e:
        return {"url": url, "baslik": baslik, "metin": "", "hata": str(e)[:150]}
    sonuc = {"url": url, "baslik": baslik, "metin": metin}
    _sayfa_onbellegi[url] = sonuc
    return sonuc


def _parcala(metin, boyut=900, ortusme=120):
    metin = " ".join(metin.split())
    return [metin[i:i + boyut] for i in range(0, max(len(metin), 1), boyut - ortusme)]


def alakali_parcalar(metin, soru, adet=3):
    """Uzun sayfadan soruya en yakın parçaları embedding ile seçer."""
    parcalar = [p for p in _parcala(metin) if len(p) > 80][:80]
    if len(parcalar) <= adet:
        return parcalar
    v = embed([soru, *parcalar])
    secilen = sorted(np.argsort(-(v[1:] @ v[0]))[:adet])  # sayfadaki sırayı koru
    return [parcalar[i] for i in secilen]


def sayfalari_oku(urller, soru, adet=3):
    """Birden çok sayfayı paralel indirir, her birinden alakalı parçaları döner."""
    if not urller:
        return []
    with ThreadPoolExecutor(max_workers=8) as havuz:
        sayfalar = list(havuz.map(sayfa_getir, urller))
    for s in sayfalar:
        s["parcalar"] = alakali_parcalar(s["metin"], soru, adet) if s["metin"] else []
    return sayfalar
