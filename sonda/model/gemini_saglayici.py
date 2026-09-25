"""Google Gemini sağlayıcısı (resmi google-genai kütüphanesi).

Ortak (Ollama) mesaj biçimini Gemini'ye çevirir; hataları kullanıcıya gösterilecek Türkçe ModelHatasi'na
dönüştürür. Anahtar hiçbir mesajda görünmez. Hata olursa sessizce yerel modele geçilmez."""
import functools
import re
import time

import httpx
from google import genai
from google.genai import errors, types

from .. import ayarlar
from . import GEMINI_ONEKI, AracCagrisi, ModelHatasi, Parca, Yanit

ZAMAN_ASIMI_MS = 120_000
YENIDEN_DENEME_BEKLEMESI = [2, 5, 10]  # 429 ve 5xx için artan bekleme (sn)
ONBELLEK_SURESI = 3600
# Kullanıcı kararı: yalnızca ucuz modeller (pahalı Pro listelenmez)
TAKMA_ADLAR = {"flash-lite": "gemini-flash-lite-latest", "flash": "gemini-flash-latest"}
ETIKETLER = {"flash-lite": "Gemini Flash-Lite (bulut, en ucuz)", "flash": "Gemini Flash (bulut, ucuz ve akıllı)"}
# Orkestratörün modelsiz eklediği araç çağrılarında düşünce imzası yoktur; Google'ın belgelediği atlama değeri
ATLAMA_IMZASI = b"skip_thought_signature_validator"

GECERSIZ = "Gemini anahtarı geçersiz ya da yetkisiz. Ayarlar'dan kontrol et."
KOTA = "Gemini istek sınırı/kotası doldu; biraz bekle ya da yerel modele geç."
SUNUCU = "Gemini şu an yanıt vermiyor."
AG = "Gemini'ye ulaşılamadı (internet bağlantısı?)."
GUVENLIK = "Gemini bu içeriği yanıtlamadı (güvenlik filtresi)."
ANAHTAR_YOK = "Gemini anahtarı kayıtlı değil. Ayarlar'dan ekle ya da yerel bir model seç."

_ANAHTAR_KALIBI = re.compile(r"AIza[0-9A-Za-z_\-]{20,}|AQ\.[0-9A-Za-z_\-]{20,}")  # eski ve yeni anahtar biçimleri
_GUVENLIK_SEBEPLERI = {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII"}
_model_onbellegi = {}


@functools.lru_cache(maxsize=4)
def _istemci(anahtar):
    """Anahtar başına tek istemci: nesne çöpe giderse bağlantısını kapatır, ayrıca bağlantı yeniden kullanılır."""
    return genai.Client(api_key=anahtar, http_options=types.HttpOptions(timeout=ZAMAN_ASIMI_MS))


def _temizle(metin, anahtar):
    metin = str(metin)
    if anahtar:
        metin = metin.replace(anahtar, "…")
    return _ANAHTAR_KALIBI.sub("…", metin)


def _anahtar():
    anahtar = ayarlar.gemini_anahtari()
    if not anahtar:
        raise ModelHatasi(ANAHTAR_YOK)
    return anahtar


# ---- dönüşümler

def _icerikler(mesajlar):
    """(sistem metni, Gemini içerikleri). Ardışık araç cevapları tek 'user' içeriğinde toplanır."""
    sistem, icerikler = [], []
    for m in mesajlar:
        rol = m.get("role")
        if rol == "system":
            sistem.append(m.get("content") or "")
            continue
        if rol == "tool":
            parca = types.Part.from_function_response(name=m.get("tool_name") or "arac",
                                                      response={"sonuc": m.get("content") or ""})
            if icerikler and icerikler[-1].role == "user" and icerikler[-1].parts[0].function_response:
                icerikler[-1].parts.append(parca)
            else:
                icerikler.append(types.Content(role="user", parts=[parca]))
            continue
        parcalar = []
        if m.get("content"):
            parcalar.append(types.Part(text=m["content"]))
        for gorsel in m.get("images") or []:
            parcalar.append(types.Part.from_bytes(data=gorsel, mime_type="image/jpeg"))
        for c in m.get("tool_calls") or []:
            parcalar.append(types.Part(function_call=types.FunctionCall(name=c["function"]["name"],
                                                                        args=dict(c["function"]["arguments"])),
                                       thought_signature=c.get("imza") or ATLAMA_IMZASI))
        icerikler.append(types.Content(role="model" if rol == "assistant" else "user",
                                       parts=parcalar or [types.Part(text=" ")]))
    if not icerikler and sistem:  # Gemini en az bir içerik ister: tek başına sistem istemi kullanıcı mesajı olur
        return None, [types.Content(role="user", parts=[types.Part(text="\n\n".join(sistem))])]
    return "\n\n".join(sistem) or None, icerikler


def _ayar(sistem, json, dusun, araclar, secenekler, dusunme_ayari=True):
    ayar = {"system_instruction": sistem}
    if json:
        ayar["response_mime_type"] = "application/json"
    if secenekler and "temperature" in secenekler:
        ayar["temperature"] = secenekler["temperature"]
    if dusunme_ayari:  # kapalıyken en düşük düzey: hız
        ayar["thinking_config"] = types.ThinkingConfig(
            thinking_level=types.ThinkingLevel.HIGH if dusun else types.ThinkingLevel.LOW,
            include_thoughts=True if dusun else None)
    if araclar:
        ayar["tools"] = [types.Tool(function_declarations=[
            types.FunctionDeclaration(name=a["function"]["name"], description=a["function"].get("description"),
                                      parameters_json_schema=a["function"].get("parameters"))
            for a in araclar])]
    return types.GenerateContentConfig(**ayar)


def _parca(yanit):
    if yanit.prompt_feedback and yanit.prompt_feedback.block_reason:
        raise ModelHatasi(GUVENLIK)
    aday = (yanit.candidates or [None])[0]
    if aday and aday.finish_reason and str(getattr(aday.finish_reason, "value", aday.finish_reason)) in _GUVENLIK_SEBEPLERI:
        raise ModelHatasi(GUVENLIK)
    metin, dusunce, cagrilar = "", "", []
    for p in (aday.content.parts if aday and aday.content and aday.content.parts else []):
        if p.function_call:
            cagrilar.append(AracCagrisi(p.function_call.name, dict(p.function_call.args or {}), p.thought_signature))
        elif p.text and p.thought:
            dusunce += p.text
        elif p.text:
            metin += p.text
    return Parca(metin, dusunce, cagrilar)


# ---- hatalar

def _cevir(h, anahtar):
    """Kütüphane hatasını (yeniden_denenebilir_mi, ModelHatasi) çiftine çevirir."""
    if isinstance(h, ModelHatasi):
        return False, h
    if isinstance(h, errors.APIError):
        mesaj = str(getattr(h, "message", "") or h)
        if h.code in (401, 403) or (h.code == 400 and re.search(r"api.?key", mesaj, re.I)):
            return False, ModelHatasi(GECERSIZ)
        if h.code == 429:
            return True, ModelHatasi(KOTA)
        if h.code >= 500:
            return True, ModelHatasi(SUNUCU)
        return False, ModelHatasi(_temizle(f"Gemini isteği reddetti ({h.code}): {mesaj[:200]}", anahtar))
    if isinstance(h, httpx.TimeoutException):
        return True, ModelHatasi(SUNUCU)
    if isinstance(h, (httpx.TransportError, OSError)):
        return False, ModelHatasi(AG)
    return False, ModelHatasi(_temizle(f"Gemini hatası: {type(h).__name__}: {h}", anahtar))


def _dusunme_desteklenmiyor(h):
    return isinstance(h, errors.ClientError) and h.code == 400 and "thinking" in str(h).lower()


def _dene(islem, anahtar):
    """islem(dusunme_ayari) -> sonuç. 429/5xx artan beklemeyle yeniden denenir; düşünme ayarını
    desteklemeyen eski modellerde ayarsız tekrar denenir."""
    dusunme_ayari = True
    for deneme in range(len(YENIDEN_DENEME_BEKLEMESI) + 1):
        try:
            return islem(dusunme_ayari)
        except Exception as h:
            hata = h
            if dusunme_ayari and _dusunme_desteklenmiyor(h):
                dusunme_ayari = False
                try:
                    return islem(False)
                except Exception as h2:
                    hata = h2
            tekrar, model_hatasi = _cevir(hata, anahtar)
            if not tekrar or deneme == len(YENIDEN_DENEME_BEKLEMESI):
                raise model_hatasi from None
            time.sleep(YENIDEN_DENEME_BEKLEMESI[deneme])


# ---- ortak arayüz

def sohbet(model, mesajlar, akis=False, json=False, dusun=False, araclar=None, secenekler=None):
    anahtar = _anahtar()
    ad = model.removeprefix(GEMINI_ONEKI)
    sistem, icerikler = _icerikler(mesajlar)
    modeller_ = _istemci(anahtar).models

    if not akis:
        def islem(dusunme_ayari):
            y = modeller_.generate_content(model=ad, contents=icerikler,
                                           config=_ayar(sistem, json, dusun, araclar, secenekler, dusunme_ayari))
            p = _parca(y)
            return Yanit(p.metin, p.arac_cagrilari)
        return _dene(islem, anahtar)

    def akis_uret():
        # Yeniden deneme yalnızca akış başlamadan: ilk parça geldikten sonra hata doğrudan yükselir
        def baslat(dusunme_ayari):
            it = iter(modeller_.generate_content_stream(
                model=ad, contents=icerikler, config=_ayar(sistem, json, dusun, araclar, secenekler, dusunme_ayari)))
            return it, next(it, None)
        it, ilk = _dene(baslat, anahtar)
        if ilk is None:
            return
        yield _parca(ilk)
        try:
            for y in it:
                yield _parca(y)
        except ModelHatasi:
            raise
        except Exception as h:
            raise _cevir(h, anahtar)[1] from None
    return akis_uret()


def anahtar_dogrula(anahtar):
    """Model listesini isteyerek anahtarı sınar; geçersizse ModelHatasi."""
    try:
        next(iter(_istemci(anahtar).models.list()), None)
    except Exception as h:
        raise _cevir(h, anahtar)[1] from None


def _surum(ad):
    m = re.fullmatch(r"gemini-(\d+(?:\.\d+)?)-(flash-lite|flash)", ad)
    return (float(m.group(1)), m.group(2)) if m else None


def _sec(adlar):
    secilen = {}
    for tur, takma in TAKMA_ADLAR.items():
        if takma in adlar:
            secilen[tur] = takma
            continue
        adaylar = [(s[0], a) for a in adlar if (s := _surum(a)) and s[1] == tur]
        secilen[tur] = max(adaylar)[1] if adaylar else takma
    return secilen


def modeller():
    """Anahtar varsa Flash-Lite ve Flash seçenekleri. Liste 1 saat önbellekte; alınamazsa takma adlar gösterilir."""
    anahtar = ayarlar.gemini_anahtari()
    if not anahtar:
        return []
    kayit = _model_onbellegi.get(anahtar)
    if not kayit or time.monotonic() - kayit[0] > ONBELLEK_SURESI:
        try:
            adlar = [m.name.removeprefix("models/") for m in _istemci(anahtar).models.list()
                     if "generateContent" in (m.supported_actions or [])]
            kayit = (time.monotonic(), _sec(adlar))
            _model_onbellegi[anahtar] = kayit
        except Exception:
            kayit = (0, dict(TAKMA_ADLAR))  # önbelleğe alınmaz: bir dahakine yeniden denenir
    return [{"ad": GEMINI_ONEKI + kayit[1][tur], "etiket": ETIKETLER[tur]} for tur in TAKMA_ADLAR]
