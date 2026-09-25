"""Modelden karar alma: görevin derinliği/planı ve her adımdaki tek eylem (JSON)."""
import json

from .. import hafiza
from .. import model as saglayici
from ..ortak import JSON_SECENEKLERI, bugun
from . import ayar
from .promptlar import BUTON_KURALI, BUTON_KURALI_SERBEST, DEGERLENDIRME_PROMPTU, DERINLIK_PROMPTU, SISTEM


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


def karar_al(model, istem, ekran=None, dusun=False, serbest=False):
    """Tek eylem kararı. dusun=True: model önce adım adım düşünür (daha yavaş, daha isabetli).
    serbest=True: kullanıcı son adım butonlarına basma izni verdi."""
    sistem = SISTEM.format(tarih=bugun(), hafiza=f"\n\n{h}" if (h := hafiza.istem_metni()) else "",
                           buton_kurali=BUTON_KURALI_SERBEST if serbest else BUTON_KURALI)
    ek = ""
    for _ in range(2):
        mesaj = {"role": "user", "content": istem + ek}
        if ekran:
            mesaj["images"] = [ekran]
        yanit = saglayici.sohbet(model, [{"role": "system", "content": sistem}, mesaj], json=True, dusun=dusun,
                                 secenekler=JSON_SECENEKLERI)
        try:
            veri = json.loads(yanit.metin)
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
        yanit = saglayici.sohbet(model, [
            {"role": "system", "content": DERINLIK_PROMPTU.format(tarih=bugun())},
            {"role": "user", "content": (f"Önceki konuşma:\n{onceki}\n\n" if onceki else "") + f"Görev: {gorev_metni}"}],
            json=True, secenekler=JSON_SECENEKLERI)
        veri = json.loads(yanit.metin)
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


def ilerleme_degerlendir(model, gorev_metni, derinlik, notlar, hafiza_):
    """Ara değerlendirme: model gidişatı düşünerek gözden geçirir ve kalan planı günceller. Hata olursa {}."""
    plan = "\n".join(f"{i}. {a}" for i, a in enumerate(derinlik["plan"], 1)) or "(plan yok)"
    icerik = (f"GÖREV: {gorev_metni}\n\nPLAN:\n{plan}\n\nNOTLAR:\n"
              + ("\n".join(f"- {n['metin']}" for n in notlar) or "(yok)")
              + f"\n\nZİYARET EDİLEN SAYFALAR:\n{hafiza_.metin()}")
    try:
        yanit = saglayici.sohbet(model, [
            {"role": "system", "content": DEGERLENDIRME_PROMPTU.format(tarih=bugun())},
            {"role": "user", "content": icerik}], json=True, dusun=True, secenekler=JSON_SECENEKLERI)
        veri = json.loads(yanit.metin)
    except Exception:
        return {}
    if not isinstance(veri, dict):
        return {}
    yeni = [a.strip() for a in veri.get("plan", []) if isinstance(a, str) and a.strip()][:6] \
        if isinstance(veri.get("plan"), list) else []
    degerlendirme = str(veri.get("degerlendirme") or "").strip()[:300]
    return {"degerlendirme": degerlendirme, "plan": yeni} if (yeni or degerlendirme) else {}
