"""Model katmanı: Sonda'nın bütün model çağrıları buradan geçer.

Ad "gemini:" ile başlıyorsa Google Gemini'ye, değilse yerel Ollama'ya gider. Mesaj biçimi Ollama'nınkidir
(role, content, images, tool_calls, tool_name); her sağlayıcı kendi biçimine çevirir."""
from dataclasses import dataclass, field

GEMINI_ONEKI = "gemini:"


class ModelHatasi(Exception):
    """Kullanıcıya olduğu gibi gösterilecek Türkçe mesaj taşır. Sessizce yerel modele geçilmez."""


@dataclass
class AracCagrisi:
    ad: str
    argumanlar: dict
    imza: bytes | None = None  # Gemini'nin düşünce imzası: çağrı geri gönderilirken aynen eklenmeli


@dataclass
class Yanit:
    metin: str = ""
    arac_cagrilari: list = field(default_factory=list)


@dataclass
class Parca:
    metin: str = ""
    dusunce: str = ""
    arac_cagrilari: list = field(default_factory=list)


def _saglayici(model):
    if model.startswith(GEMINI_ONEKI):
        from . import gemini_saglayici
        return gemini_saglayici
    from . import ollama_saglayici
    return ollama_saglayici


def sohbet(model, mesajlar, akis=False, json=False, dusun=False, araclar=None, secenekler=None):
    """akis=False -> Yanit; akis=True -> Parca akışı."""
    return _saglayici(model).sohbet(model, mesajlar, akis=akis, json=json, dusun=dusun, araclar=araclar,
                                    secenekler=secenekler)


# Ollama sağlayıcısı hemen yüklenir: ollama.embed/list/ps (web.py, sunucu.py) zaman sınırlı istemciye bağlansın
from . import ollama_saglayici  # noqa: E402,F401
