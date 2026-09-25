"""Görev modunun güvenlik kuralları. Modelin kararı ne olursa olsun, tarayıcıya giden her eylem buradan geçer.

Kart, şifre ve doğrulama kodu alanlarına yazılmaz; ödeme, gönderme, silme, onaylama ve giriş butonlarına
basılmaz. Bunlar kullanıcıya bırakılır. Kurallar temkinlidir: şüpheli durumda engellemek, yanlışlıkla
ödeme yapmaktan iyidir.

Tek istisna (kullanıcı kararı): kullanıcı görev mesajında bir sitenin şifresini açıkça verdiyse, o şifre ve yalnızca
o şifre, yalnızca görevde adı geçen sitede şifre alanına yazılabilir ve giriş butonuna basılabilir. Kart, CVV, IBAN
ve doğrulama kodları görevde verilse bile kullanıcıya kalır.
"""
import re
from dataclasses import dataclass
from urllib.parse import unquote, urlparse

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

_GIRIS_BUTONU = re.compile(r"giris yap|oturum ac|\bsign ?in\b|\blog ?in\b")
_SIFRE = re.compile(r"sifre|parola|passw")
_KART_VEYA_KOD = re.compile(r"kart|card|cvv|cvc|\bcsc\b|guvenlik kodu|security code|son kullanma|expir|\biban\b|\bpin\b"
                            r"|\botp\b|dogrulama|verification|onay kodu|sms kod|\bcc (num|number|exp|csc|name)")
_IKINCI_SEVIYE = {"com", "gov", "org", "net", "edu", "co", "ac", "bel", "k12", "av", "gen", "web", "info", "biz",
                  "tv", "tsk", "pol", "dr", "name"}

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


def _site_adi(url):
    """Adresin kayıtlı alan adındaki ayırt edici etiket: www.upwork.com -> upwork, giris.turkiye.gov.tr -> turkiye.
    IP ve localhost için tam ana makine adı."""
    host = (urlparse(url).hostname or "").lower()
    etiketler = host.split(".")
    if len(etiketler) < 2 or host.replace(".", "").isdigit():
        return host
    if len(etiketler) >= 3 and len(etiketler[-1]) == 2 and etiketler[-2] in _IKINCI_SEVIYE:
        return etiketler[-3]
    return etiketler[-2]


def _kimlik_gorevi(gorev_metni, url):
    """Görev şifre veriyor ve şu anki site görevde adıyla geçiyor mu?"""
    ad = _site_adi(url)
    if not ad or not _SIFRE.search(sade(gorev_metni)):
        return False
    if "." in ad or ad == "localhost":
        return ad in gorev_metni.lower()
    return bool(re.search(rf"\b{re.escape(ad)}\b", sade(gorev_metni)))


def _sifre_alani(oge):
    """Kart ya da doğrulama kodu olmayan, düz şifre alanı."""
    metin = sade(" ".join(str(oge.get(k) or "") for k in ("metin", "ad", "kimlik", "yer", "aria")))
    otomatik = oge.get("otomatik") or ""
    if otomatik.startswith("cc-") or otomatik == "one-time-code" or _KART_VEYA_KOD.search(metin):
        return False
    return oge.get("tip") == "password" or otomatik in ("current-password", "new-password") or bool(_SIFRE.search(metin))


# Sıradan kelime (harf, arada - ya da ' olabilir): "ile", "upwork'e", "e-posta" şifre adayı sayılmaz
_KELIME = re.compile(r"[^\W\d_]+([-'][^\W\d_]+)*")


def gizli_adaylar(gorev_metni):
    """Görev metninde şifre sözcüğünün yakınında (3 kelime) geçen, şifreye benzeyen değerler."""
    temiz = [k.strip("'\"“”‘’.,;:()") for k in str(gorev_metni or "").split()]
    adaylar = set()
    for i, k in enumerate(temiz):
        if not _SIFRE.search(sade(k)):
            continue
        for a in temiz[max(0, i - 3):i] + temiz[i + 1:i + 4]:
            if len(a) >= 4 and "@" not in a and "://" not in a and not _KELIME.fullmatch(a):
                adaylar.add(a)
    return adaylar


def _gizli_iceriyor(metin, gizliler):
    metin = unquote(unquote(str(metin or "")))
    return any(g in metin for g in gizliler if len(g) >= 4)


def _submit_mu(oge):
    if oge.get("form", -1) < 0:
        return False
    return (oge.get("etiket") == "button" and oge.get("tip") in ("", "submit")) or \
           (oge.get("etiket") == "input" and oge.get("tip") in ("submit", "image"))


def kontrol(eylem, oge=None, form_ogeleri=(), gorev_metni="", url="", gizliler=()):
    ad = eylem.get("eylem")
    gizli = set(gizliler) | gizli_adaylar(gorev_metni)
    if ad == "git":
        hedef = str(eylem.get("url") or "").strip()
        if urlparse(hedef).scheme not in ("http", "https"):
            return Karar(False, f"Yalnızca http ve https adreslerine gidilebilir: {hedef[:80]}")
        if _gizli_iceriyor(hedef, gizli):
            return Karar(False, "🔒 Bu adres görevde verdiğin şifreyi içeriyor; şifre hiçbir adrese yazılamaz.")
        return Karar(True)
    if ad in ("yaz", "sec"):
        deger = str(eylem.get("metin") or eylem.get("deger") or "")
        if hassas_alan(oge) and _sifre_alani(oge) and len(deger) >= 4 and deger in gorev_metni                 and _kimlik_gorevi(gorev_metni, url):
            return Karar(True)
        if _gizli_iceriyor(deger, gizli):
            return Karar(False, "🔒 Görevde verdiğin şifre yalnızca o sitenin şifre alanına yazılabilir.")
        if hassas_alan(oge):
            return Karar(False, f"🔒 “{oge_adi(oge)}” hassas bir alan. Kart, şifre ve doğrulama bilgilerini sen girmelisin.")
        return Karar(True, enter=ad == "yaz" and bool(eylem.get("enter")) and arama_kutusu(oge))
    if ad == "tikla":
        kimlik = _kimlik_gorevi(gorev_metni, url)
        metin = sade(" ".join(str(oge.get(k) or "") for k in ("metin", "deger", "aria", "baslik")))
        if kimlik and _GIRIS_BUTONU.search(metin) and not _YASAK_BUTON.search(_GIRIS_BUTONU.sub(" ", metin)):
            return Karar(True)
        if yasak_buton(oge):
            return Karar(False, f"🔒 “{oge_adi(oge)}” son adım butonu. Kontrol edip buna sen basmalısın.")
        hassaslar = [f for f in form_ogeleri if hassas_alan(f)]
        if _submit_mu(oge) and hassaslar and not (kimlik and all(_sifre_alani(f) for f in hassaslar)):
            return Karar(False, f"🔒 “{oge_adi(oge)}” kart veya şifre içeren bir formu gönderiyor. Bu adım senin.")
        return Karar(True)
    return Karar(True)
