"""Görev modunun güvenlik kuralları. Modelin kararı ne olursa olsun, tarayıcıya giden her eylem buradan geçer.

Kart, şifre ve doğrulama kodu alanlarına yazılmaz; ödeme, gönderme, silme, onaylama ve giriş butonlarına
basılmaz. Bunlar kullanıcıya bırakılır. Kurallar temkinlidir: şüpheli durumda engellemek, yanlışlıkla
ödeme yapmaktan iyidir.
"""
import re
from dataclasses import dataclass
from urllib.parse import urlparse

_TR = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")

_HASSAS = re.compile(
    r"kart|card|cvv|cvc|\bcsc\b|guvenlik kodu|security code|son kullanma|expir|\bexp ?(month|year|date|mm|yy)"
    r"|\biban\b|sifre|parola|passw|\bpin\b|\botp\b|dogrulama|verification|onay kodu|sms kod|\bcc (num|number|exp|csc|name)")
_HASSAS_OTOMATIK = re.compile(r"^cc-|^(current|new)-password$|^one-time-code$")

_YASAK_BUTON = re.compile(
    r"\bode\b|\bodeme(yi)? (yap|tamamla|onayla)|\bodemeye gec|satin al|hemen al|simdi al"
    r"|\bsiparis(i)? (ver|onayla|tamamla)|alisverisi tamamla|\bgonder|\bbasvur|\bsil\b|\bkaldir"
    r"|hesabi (kapat|sil)|\bonayla|giris yap|oturum ac|uye ol|kayit ol|abone ol"
    r"|\bpay\b|\bbuy\b|purchase|place order|\bcheck ?out\b|\bsubmit|\bsend\b|\bapply\b|\bdelete\b|\bremove\b"
    r"|\bconfirm|\bsign ?(in|up)\b|\blog ?in\b|\bregister|subscribe")

_ARAMA_ADLARI = {"q", "query", "search", "s", "ara", "arama", "k", "keyword", "keywords", "search query", "searchterm"}
_ARAMA_EYLEMI = re.compile(r"search|\bara(ma)?\b")


@dataclass
class Karar:
    izin: bool
    sebep: str = ""
    enter: bool = False


def sade(metin):
    """Karşılaştırma için: camelCase ayrılır, Türkçe harfler düzleşir, küçük harf, _ - ve boşluklar tek boşluk."""
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", str(metin or "")).translate(_TR).lower()
    return re.sub(r"[\s_\-]+", " ", s).strip()


def oge_adi(oge):
    for k in ("metin", "aria", "deger", "yer", "baslik", "ad"):
        if oge.get(k):
            return str(oge[k])[:60]
    return oge.get("etiket", "öğe")


def arama_kutusu(oge):
    if oge.get("tip") == "search" or oge.get("rol") == "searchbox":
        return True
    if sade(oge.get("ad")) in _ARAMA_ADLARI:
        return True
    return oge.get("form", -1) >= 0 and bool(_ARAMA_EYLEMI.search(sade(oge.get("form_eylem"))))


def hassas_alan(oge):
    if oge.get("tip") == "password" or _HASSAS_OTOMATIK.search(oge.get("otomatik") or ""):
        return True
    if oge.get("tip") == "search" or oge.get("rol") == "searchbox":
        return False
    return bool(_HASSAS.search(sade(" ".join(str(oge.get(k) or "") for k in ("metin", "ad", "kimlik", "yer", "aria")))))


def yasak_buton(oge):
    return bool(_YASAK_BUTON.search(sade(" ".join(str(oge.get(k) or "") for k in ("metin", "deger", "aria", "baslik")))))


def _submit_mu(oge):
    if oge.get("form", -1) < 0:
        return False
    return (oge.get("etiket") == "button" and oge.get("tip") in ("", "submit")) or \
           (oge.get("etiket") == "input" and oge.get("tip") in ("submit", "image"))


def kontrol(eylem, oge=None, form_ogeleri=()):
    ad = eylem.get("eylem")
    if ad == "git":
        url = str(eylem.get("url") or "").strip()
        if urlparse(url).scheme not in ("http", "https"):
            return Karar(False, f"Yalnızca http ve https adreslerine gidilebilir: {url[:80]}")
        return Karar(True)
    if ad in ("yaz", "sec"):
        if hassas_alan(oge):
            return Karar(False, f"🔒 “{oge_adi(oge)}” hassas bir alan. Kart, şifre ve doğrulama bilgilerini sen girmelisin.")
        return Karar(True, enter=ad == "yaz" and bool(eylem.get("enter")) and arama_kutusu(oge))
    if ad == "tikla":
        if yasak_buton(oge):
            return Karar(False, f"🔒 “{oge_adi(oge)}” son adım butonu. Kontrol edip buna sen basmalısın.")
        if _submit_mu(oge) and any(hassas_alan(f) for f in form_ogeleri):
            return Karar(False, f"🔒 “{oge_adi(oge)}” kart veya şifre içeren bir formu gönderiyor. Bu adım senin.")
        return Karar(True)
    return Karar(True)
