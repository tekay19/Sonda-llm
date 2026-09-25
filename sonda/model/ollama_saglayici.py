"""Yerel Ollama sağlayıcısı."""
import ollama

from . import AracCagrisi, Parca, Yanit

# Takılan bir çağrı görev işçisini (ve sonraki tüm görevleri) kilitlemesin. Düşünme modundaki uzun analizler
# işlemcide dakikalar sürebildiği için sınır cömert. embed/list/ps de aynı istemciyi kullanır.
ZAMAN_ASIMI = 900
_istemci = ollama.Client(timeout=ZAMAN_ASIMI)
ollama.chat, ollama.embed, ollama.list, ollama.ps = _istemci.chat, _istemci.embed, _istemci.list, _istemci.ps


def _cagrilar(tool_calls):
    return [AracCagrisi(c.function.name, dict(c.function.arguments)) for c in tool_calls or []]


def _hazirla(mesajlar):
    """Ortak biçimdeki Gemini'ye özgü 'imza' alanını çıkarır."""
    hazir = []
    for m in mesajlar:
        if m.get("tool_calls"):
            m = {**m, "tool_calls": [{"function": c["function"]} for c in m["tool_calls"]]}
        hazir.append(m)
    return hazir


def sohbet(model, mesajlar, akis=False, json=False, dusun=False, araclar=None, secenekler=None):
    yanit = _istemci.chat(model=model, messages=_hazirla(mesajlar), stream=akis, think=dusun,
                          format="json" if json else None, tools=araclar, options=secenekler)
    if not akis:
        return Yanit(yanit.message.content or "", _cagrilar(yanit.message.tool_calls))
    return (Parca(p.message.content or "", getattr(p.message, "thinking", None) or "", _cagrilar(p.message.tool_calls))
            for p in yanit)
