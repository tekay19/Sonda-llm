"""Modelden karar alma: görevin derinliği/planı ve her adımdaki tek eylem (JSON)."""
import json

import ollama

from .. import hafiza
from ..ortak import JSON_SECENEKLERI, bugun
from . import ayar
from .promptlar import DERINLIK_PROMPTU, SISTEM


def dogrula(veri):
    """Hata metni ya da None döner; 'no' alanını tamsayıya çevirir."""
    if not isinstance(veri, dict) or veri.get("eylem") not in ayar.EYLEMLER:
        return f"'eylem' şunlardan biri olmalı: {', '.join(ayar.EYLEMLER)}"
    for alan in ayar.EYLEMLER[veri["eylem"]]:
        if veri.get(alan) in (None, ""):
            return f"'{veri['eylem']}' eylemi için '{alan}' gerekli"
    if "no" in ayar.EYLEMLER[veri["eylem"]]:
        try:
            veri["no"] = int(str(veri["no"]).strip("[] "))
        except ValueError:
            return "'no' öğe numarası (tamsayı) olmalı"
    return None


def karar_al(model, istem, ekran=None):
    sistem = SISTEM.format(tarih=bugun(), hafiza=f"\n\n{h}" if (h := hafiza.istem_metni()) else "")
    ek = ""
    for _ in range(2):
        mesaj = {"role": "user", "content": istem + ek}
        if ekran:
            mesaj["images"] = [ekran]
        yanit = ollama.chat(model=model, format="json", think=False, options=JSON_SECENEKLERI,
                            messages=[{"role": "system", "content": sistem}, mesaj])
        try:
            veri = json.loads(yanit.message.content)
        except json.JSONDecodeError:
            veri = None
        hata = dogrula(veri)
        if not hata:
            return veri
        ek = f"\n\nÖNCEKİ CEVABIN GEÇERSİZDİ: {hata}. Sadece geçerli JSON döndür."
    return None


def derinlik_belirle(model, gorev_metni, onceki):
    """Görevin ne kadar derin araştırılacağını ve planını modele sorar; hatalı cevabı düzeltir."""
    try:
        yanit = ollama.chat(model=model, format="json", think=False, options=JSON_SECENEKLERI, messages=[
            {"role": "system", "content": DERINLIK_PROMPTU.format(tarih=bugun())},
            {"role": "user", "content": (f"Önceki konuşma:\n{onceki}\n\n" if onceki else "") + f"Görev: {gorev_metni}"}])
        veri = json.loads(yanit.message.content)
    except Exception:
        veri = {}
    if not isinstance(veri, dict):
        veri = {}
    derinlik = veri.get("derinlik") if veri.get("derinlik") in ayar.ADIM_SINIRI else "orta"
    try:
        min_site = int(veri.get("min_site", 2))
    except (TypeError, ValueError):
        min_site = 2
    plan = veri.get("plan") if isinstance(veri.get("plan"), list) else []
    plan = [a.strip() for a in plan if isinstance(a, str) and a.strip()][:6]
    return {"derinlik": derinlik, "min_site": max(1, min(5, min_site)), "inceleme": veri.get("inceleme") is True,
            "maks_adim": min(ayar.MAKS_ADIM, ayar.ADIM_SINIRI[derinlik]), "plan": plan}
