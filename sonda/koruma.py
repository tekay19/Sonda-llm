"""Görev modunun güvenlik kuralları. Modelin kararı ne olursa olsun, tarayıcıya giden her eylem buradan geçer.

Kart, şifre ve doğrulama kodu alanlarına yazılmaz; ödeme, gönderme, silme, onaylama ve giriş butonlarına
basılmaz. Bunlar kullanıcıya bırakılır. Kurallar temkinlidir: şüpheli durumda engellemek, yanlışlıkla
ödeme yapmaktan iyidir.

Tek istisna (kullanıcı kararı): kullanıcı görev mesajında bir sitenin şifresini açıkça verdiyse, o şifre ve yalnızca
o şifre, yalnızca görevde adı geçen sitede şifre alanına yazılabilir ve giriş butonuna basılabilir. Kart, CVV, IBAN
ve doğrulama kodları görevde verilse bile kullanıcıya kalır.
"""
import base64
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
    r"|\bconfirm|\bsign ?(in|up)\b|\blog ?in\b|\bregister|subscribe"
    # gerçek sitelerin son adım etiketleri (final inceleme: Amazon "Siparişinizi verin", "Place your order"...)
    r"|\bsiparis\w* (ver|onayla|tamamla)|place (your )?order|\b(complete|confirm|submit) (my |your )?(order|purchase|booking|payment)"
    r"|\border now\b|\bbook now\b|rezervasyon\w* (yap|tamamla|onayla)|\bodeme\w* (devam|gec)|teklif\w* kabul"
    r"|accept (the )?offer|\bhire\b|\bise al|\bbagis|donate|transfer et|havale|\beft\b|para gonder|send money")
# Ödeme/sipariş sayfalarında "Devam/Continue" da son adım olabilir (kayıtlı kartla tek tık sipariş)
_ODEME_ADRESI = re.compile(r"checkout|/odeme|/payment|/buy/|/siparis|place-?order|/sepet/onay|/cart/confirm", re.I)
_DEVAM = re.compile(r"(devam( et)?|continue|ileri|next|proceed( to [a-z ]+)?)")

_ALAN_ADI = re.compile(r"(?<![@\w.-])((?:[a-z0-9-]+\.)+[a-z]{2,})")
_UZANTILAR = {"com", "net", "org", "tr", "io", "co", "ai", "dev", "app", "gov", "edu", "info", "biz", "me", "uk", "de",
              "fr", "nl", "eu", "us", "ca", "au", "ru", "xyz", "shop", "store", "site", "online", "tech", "cloud", "tv"}


def _alan_adi_mi(parca):
    """Gerçek bir uzantıyla biten alan adı mı? ("upwork.com" evet, şifre "Gizli.Sifre-42" hayır)"""
    m = re.fullmatch(r"(?:[a-z0-9-]+\.)+([a-z]{2,})", parca.lower())
    return bool(m) and m.group(1) in _UZANTILAR


_GIRIS_ALTLARI = {"", "www", "accounts", "account", "login", "auth", "signin", "sso", "id", "secure", "giris", "oturum"}
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


def _kayitli_alan(host):
    """(kayıtlı alan adı, alt alan etiketleri): giris.turkiye.gov.tr -> ("turkiye.gov.tr", ["giris"])."""
    e = host.split(".")
    if len(e) >= 3 and len(e[-1]) == 2 and e[-2] in _IKINCI_SEVIYE:
        return ".".join(e[-3:]), e[:-3]
    return ".".join(e[-2:]), e[:-2]


def _kimlik_gorevi(gorev_metni, url):
    """Görev şifre veriyor ve şu anki site görevdeki site mi? Tam kayıtlı alan adı karşılaştırılır
    (upwork.xyz, upwork.com.evil.io ve docs.google.com gibi alt alanlar geçmez)."""
    host = (urlparse(url).hostname or "").lower()
    if not host or not _SIFRE.search(sade(gorev_metni)):
        return False
    metin = gorev_metni.lower()
    if host == "localhost" or host.replace(".", "").isdigit():
        return host in metin
    alan, alt = _kayitli_alan(host)
    if ".".join(alt) not in _GIRIS_ALTLARI:  # docs., forms., kullanıcı alt alanları: ancak görevde aynen yazıyorsa
        return host in metin
    for gizli in gizli_adaylar(gorev_metni):  # "Gizli.Sifre-42" gibi şifreler alan adı sanılmasın
        metin = metin.replace(gizli.lower(), " ")
    yazilan = {_kayitli_alan(a)[0] for a in _ALAN_ADI.findall(metin) if _alan_adi_mi(a)}
    if yazilan:
        return alan in yazilan
    etiket = alan.split(".")[0]
    return alan in (f"{etiket}.com", f"{etiket}.com.tr") and bool(re.search(rf"\b{re.escape(etiket)}\b", sade(gorev_metni)))


def _sifre_alani(oge):
    """Kart ya da doğrulama kodu olmayan, düz şifre alanı."""
    metin = sade(" ".join(str(oge.get(k) or "") for k in ("metin", "ad", "kimlik", "yer", "aria")))
    otomatik = oge.get("otomatik") or ""
    if otomatik.startswith("cc-") or otomatik == "one-time-code" or _KART_VEYA_KOD.search(metin):
        return False
    return oge.get("tip") == "password" or otomatik in ("current-password", "new-password") or bool(_SIFRE.search(metin))


# Sıradan kelime (harf, arada - ya da ' olabilir): "ile", "upwork'e", "e-posta" şifre adayı sayılmaz
_KELIME = re.compile(r"[^\W\d_]+([-'][^\W\d_]+)*")


# Şifre sözcüğünden hemen sonra gelse de şifre olmayan kelimeler ("şifremle giriş yap", "password is ...")
_DURAK = {"ile", "ve", "olarak", "is", "for", "to", "gir", "giris", "yap", "kullan", "bu", "su", "benim", "my", "the",
          "hesabima", "hesap", "unuttum", "sifirla", "degistir", "yok", "alani", "alanina", "girme", "girmeden"}


def _kesin_aday(a):
    return len(a) >= 4 and "@" not in a and "://" not in a and not _alan_adi_mi(a) and sade(a) not in _DURAK \
        and not _SIFRE.search(sade(a))


def gizli_adaylar(gorev_metni):
    """Görevde verilen şifreler: şifre sözcüğünden hemen sonraki kelime (şekli ne olursa olsun: "sunflower",
    "correct-horse-battery") ve yakınındaki (3 kelime) şifreye benzeyen değerler ("'abc123' şifresiyle")."""
    temiz = [k.strip("'\"“”‘’.,;:()") for k in str(gorev_metni or "").split()]
    adaylar = set()
    for i, k in enumerate(temiz):
        if not _SIFRE.search(sade(k)):
            continue
        j = i + 1
        while j < len(temiz) and sade(temiz[j]) in ("is", "olarak", ""):
            j += 1
        if j < len(temiz) and _kesin_aday(temiz[j]):
            adaylar.add(temiz[j])
        for a in temiz[max(0, i - 3):i] + temiz[i + 1:i + 4]:
            if len(a) >= 4 and "@" not in a and "://" not in a and not _KELIME.fullmatch(a) and not _alan_adi_mi(a):
                adaylar.add(a)
    return adaylar


def _gizli_iceriyor(metin, gizliler):
    """Şifrenin tamamı, yarısından uzun bir parçası (büyük/küçük harf fark etmez), base64 ya da hex hali geçiyor mu?"""
    metin = unquote(unquote(str(metin or ""))).lower()
    for g in gizliler:
        if len(g) < 4:
            continue
        n = max(4, len(g) // 2)
        kucuk = g.lower()
        if any(kucuk[i:i + n] in metin for i in range(len(kucuk) - n + 1)):
            return True
        kodlar = (base64.b64encode(g.encode()).decode().rstrip("=").lower(), g.encode().hex())
        if any(kod[:max(8, len(kod) // 2)] in metin for kod in kodlar):
            return True
    return False


def gizle(metin, gizliler):
    """Çıktılarda şifreleri ••• ile değiştirir."""
    metin = str(metin or "")
    for g in gizliler:
        if len(g) >= 4:
            metin = re.sub(re.escape(g), "•••", metin, flags=re.I)
    return metin


YER_TUTUCU = re.compile(r"\{SIFRE_\d+\}")


def yer_tutucular(metin):
    """Görevdeki şifreler için {SIFRE_1}, {SIFRE_2}...: model yalnızca bunları görür, gerçek değeri kod yazar."""
    metin = str(metin or "")
    adaylar = sorted(gizli_adaylar(metin), key=lambda a: (metin.find(a), -len(a)))
    return {f"{{SIFRE_{i}}}": a for i, a in enumerate(adaylar, 1)}


def yer_tut(metin, harita):
    metin = str(metin or "")
    for tutucu, gizli in sorted(harita.items(), key=lambda x: -len(x[1])):  # uzun şifre önce: iç içe geçmesin
        metin = re.sub(re.escape(gizli), tutucu, metin, flags=re.I)
    return metin


def _enter_guvenli(form_ogeleri):
    """Enter formun varsayılan butonunu tetikler: hassas alan yoksa ve form küçük bir arama formuysa güvenli."""
    if any(hassas_alan(f) for f in form_ogeleri):
        return False
    yazilabilir = [f for f in form_ogeleri if f.get("etiket") == "textarea" or
                   (f.get("etiket") == "input" and f.get("tip") in ("", "text", "search", "email", "tel", "number", "url"))]
    return len(yazilabilir) <= 2


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
        return Karar(True, enter=ad == "yaz" and bool(eylem.get("enter")) and arama_kutusu(oge)
                     and _enter_guvenli(form_ogeleri))
    if ad == "tikla":
        kimlik = _kimlik_gorevi(gorev_metni, url)
        metin = sade(" ".join(str(oge.get(k) or "") for k in ("metin", "deger", "aria", "baslik")))
        if kimlik and _GIRIS_BUTONU.search(metin) and not _YASAK_BUTON.search(_GIRIS_BUTONU.sub(" ", metin)):
            return Karar(True)
        if yasak_buton(oge):
            return Karar(False, f"🔒 “{oge_adi(oge)}” son adım butonu. Kontrol edip buna sen basmalısın.")
        if _ODEME_ADRESI.search(url or "") and (_submit_mu(oge) or _DEVAM.fullmatch(sade(oge_adi(oge)))):
            return Karar(False, f"🔒 Ödeme sayfasında “{oge_adi(oge)}” siparişi tamamlayabilir. Bu adım senin.")
        hassaslar = [f for f in form_ogeleri if hassas_alan(f)]
        if _submit_mu(oge) and hassaslar and not (kimlik and all(_sifre_alani(f) for f in hassaslar)):
            return Karar(False, f"🔒 “{oge_adi(oge)}” kart veya şifre içeren bir formu gönderiyor. Bu adım senin.")
        return Karar(True)
    return Karar(True)
