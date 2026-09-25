# Gemini Sağlayıcı Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sonda yerel Ollama modellerinin yanında Google Gemini API ile de bütün modlarda (hızlı, derin, görev, yönlendirme) çalışsın; görevde verilen şifre hiçbir modele gitmesin.

**Architecture:** Yeni `sonda/model/` paketi ortak `sohbet(...)` arayüzünü sunar ve `gemini:` önekine göre Ollama ya da Gemini sağlayıcısına yönlendirir. Bütün çağıranlar (`ortak.json_sor`, araştırma modları, görev karar/sonuç) bu arayüze taşınır. Görevde şifre `{SIFRE_n}` yer tutucusuyla modele gider; gerçek değeri kod, yazmadan hemen önce koyar.

**Tech Stack:** Python 3.11, FastAPI, `ollama==0.6.2`, `google-genai==1.65.0`, pytest, Playwright; arayüz tek dosya `static/index.html`.

**Spec:** `docs/superpowers/specs/2026-09-25-gemini-saglayici-design.md`

## Global Constraints

- Testler sanal ortamla çalışır: `.venv/Scripts/python -m pytest` (sistem Python'unda `ollama` yok).
- `gemini:` ile başlayan model adları Gemini'ye, diğer bütün adlar Ollama'ya gider.
- Sessiz geçiş yok: Gemini hata verirse yerel modele geçilmez; `ModelHatasi` Türkçe mesajıyla kullanıcıya gösterilir.
- Görevde verilen şifre hiçbir modele (yerel ya da Gemini) gitmez; model yalnızca `{SIFRE_1}`, `{SIFRE_2}` görür.
- API anahtarı `veri/ayarlar.json` dosyasında durur (`veri/` zaten `.gitignore`'da); `GEMINI_API_KEY` ortam değişkeni yedektir; arayüzden kaydedilen önceliklidir.
- Anahtarın tamamı hiçbir yanıtta, kayıtta, hata mesajında ya da olayda görünmez.
- Embedding (`bge-m3`) yerelde kalır; `web.py`'deki `ollama.embed` değişmez.
- Hata mesajları (aynen):
  - `"Gemini anahtarı geçersiz ya da yetkisiz. Ayarlar'dan kontrol et."`
  - `"Gemini istek sınırı/kotası doldu; biraz bekle ya da yerel modele geç."`
  - `"Gemini şu an yanıt vermiyor."`
  - `"Gemini'ye ulaşılamadı (internet bağlantısı?)."`
  - `"Gemini bu içeriği yanıtlamadı (güvenlik filtresi)."`
- Arayüz etiketleri: `"Gemini Flash (bulut, hızlı)"`, `"Gemini Pro (bulut, en akıllı)"`.
- Kod yorumları ve adlar Türkçe, mevcut dosyaların üslubunda (kısa, “neden”i anlatan yorumlar).
- Her görevin sonunda bütün test paketi yeşil olmalı (başlangıç: 376 geçti, 9 seçilmedi).

## Review Focus

1. **Gemini 3 düşünce imzası:** Araç çağrısı içeren asistan mesajı geri gönderilirken `thought_signature` eksikse Gemini 400 verir. Orkestratörün kendi uydurduğu çağrılarda (hızlı moddaki ilk `web_ara`/`sayfa_oku`) imza yoktur; bunlara `b"skip_thought_signature_validator"` konmalı. Test: Task 2 `test_imzasiz_arac_cagrisina_atlama_imzasi_konur`.
2. **Akışın ortasında hata:** Akışta ilk parça geldikten sonra 429/5xx olursa yeniden deneme yapılmamalı (kullanıcı metni iki kez görür); `ModelHatasi` yükselmeli. Test: Task 2 `test_akis_ilk_parcadan_sonra_yeniden_denenmez`.
3. **Görev mesajındaki şifre yönlendirme ve başlık çağrılarıyla sızabilir:** `yon_belirle`, `/api/baslik` ve sonraki sohbet/hızlı modlara giden geçmiş, görev modeline gitmeden önce gizlenmeli. Test: Task 4 `test_yonlendirme_ve_gecmis_sifreyi_gormez`, `test_baslik_sifreyi_gormez`.
4. **Yer tutucu yanlış yerde:** Model `{SIFRE_1}`'i e-posta alanına, bir adrese ya da görevde adı geçmeyen sitenin şifre alanına yazmaya çalışırsa engellenmeli ve gerçek şifre hiçbir yere yazılmamalı. Test: Task 4 `test_yer_tutucu_baska_alana_yazilamaz`, `test_yer_tutucu_adrese_konamaz`, `test_yer_tutucu_baska_sitede_yazilamaz`.
5. **Görev sırasında kota biterse notlar kaybolmamalı:** `karar_al` ya da `sonuc_yaz` `ModelHatasi` verirse görev "hata" durumuyla biter, cevap modelsiz yazılır (hata + notlar). Test: Task 3 `test_gorevde_model_hatasi_notlari_korur`, `test_sonuc_yazarken_model_hatasi`.

---

## File Structure

| Dosya | Durum | Sorumluluk |
|---|---|---|
| `sonda/model/__init__.py` | Yeni | `sohbet`, `Yanit`, `Parca`, `AracCagrisi`, `ModelHatasi`; `gemini:` önekine göre yönlendirme |
| `sonda/model/ollama_saglayici.py` | Yeni | Zaman sınırlı Ollama istemcisi, yanıtı ortak tiplere çevirme |
| `sonda/model/gemini_saglayici.py` | Yeni | Mesaj/görsel/araç/JSON/düşünme dönüşümü, yeniden deneme, hata çevirisi, anahtar temizleme, model listesi |
| `sonda/ayarlar.py` | Yeni | `veri/ayarlar.json` okuma/yazma; Gemini anahtarı |
| `sonda/ortak.py` | Değişir | `json_sor` yeni arayüzü kullanır; Ollama istemci kurulumu sağlayıcıya taşınır |
| `sonda/arastirma/hizli.py`, `derin.py`, `sohbet.py` | Değişir | Yeni arayüz |
| `sonda/gorev/karar.py`, `dongu.py` | Değişir | Yeni arayüz, ModelHatasi, şifre yer tutucu |
| `sonda/koruma.py` | Değişir | `yer_tutucular`, `yer_tut` |
| `sonda/asistan.py`, `sonda/yonlendirme.py` | Değişir | ModelHatasi mesajı, geçmişte şifre gizleme |
| `sonda/sunucu.py` | Değişir | `/api/ayarlar` uç noktaları, Gemini modellerini listeleme, başlıkta şifre gizleme |
| `static/index.html` | Değişir | "Ayarlar" çekmecesi, hata ipucu |
| `tests/test_model.py` | Yeni | Yönlendirme, Ollama dönüşümü |
| `tests/test_gemini.py` | Yeni | Gemini sağlayıcı birim testleri (sahte istemci) |
| `tests/test_ayarlar.py` | Yeni | Anahtar saklama ve uç noktalar |
| `tests/test_gemini_gercek.py` | Yeni | `-m gemini` gerçek API testleri |
| `tests/test_gorev.py`, `tests/test_sunucu.py`, `tests/test_arayuz.py` | Değişir | Yamalama noktaları, yeni testler |
| `requirements.txt`, `pytest.ini` | Değişir | `google-genai==1.65.0`, `gemini` işareti |

---

### Task 1: `sonda/model` paketi ve Ollama sağlayıcısı; bütün çağıranların taşınması

Davranış değişmez; bu bir yeniden düzenlemedir. Bütün mevcut testler geçmeli.

**Files:**
- Create: `sonda/model/__init__.py`, `sonda/model/ollama_saglayici.py`, `tests/test_model.py`
- Modify: `sonda/ortak.py`, `sonda/arastirma/hizli.py`, `sonda/arastirma/derin.py`, `sonda/arastirma/sohbet.py`, `sonda/gorev/karar.py`, `sonda/gorev/dongu.py`, `tests/test_gorev.py`

**Interfaces:**
- Produces:
  - `sonda.model.sohbet(model: str, mesajlar: list[dict], akis=False, json=False, dusun=False, araclar=None, secenekler=None)` → `akis=False`: `Yanit`; `akis=True`: `Iterator[Parca]`
  - `Yanit(metin: str, arac_cagrilari: list[AracCagrisi])`, `Parca(metin: str, dusunce: str, arac_cagrilari: list[AracCagrisi])` (dataclass, varsayılanlar `""` / `[]`)
  - `AracCagrisi(ad: str, argumanlar: dict, imza: bytes | None = None)`
  - `ModelHatasi(Exception)` — `str(h)` kullanıcıya gösterilecek Türkçe mesajdır
  - `sonda.model.GEMINI_ONEKI = "gemini:"`
  - Ortak mesaj biçimi (Ollama biçimi): `{"role": "system|user|assistant|tool", "content": str, "images": [bytes], "tool_calls": [{"function": {"name", "arguments"}, "imza": bytes|None}], "tool_name": str}`
  - `sonda.model.ollama_saglayici._istemci` (zaman sınırlı `ollama.Client`), `ZAMAN_ASIMI = 900`
- Consumes: yok

- [ ] **Step 1: Yönlendirme ve Ollama dönüşüm testlerini yaz**

`tests/test_model.py`:

```python
"""Model katmanı: sağlayıcı seçimi ve Ollama yanıtının ortak tiplere çevrilmesi."""
from types import SimpleNamespace as NS

import pytest

from sonda import model
from sonda.model import ollama_saglayici


def test_gemini_oneki_geminiye_digerleri_ollamaya(monkeypatch):
    cagri = []
    monkeypatch.setattr(model, "_saglayici", lambda ad: cagri.append(ad) or NS(sohbet=lambda *a, **k: "ok"))
    assert model.sohbet("gemini:gemini-flash-latest", []) == "ok"
    assert cagri == ["gemini:gemini-flash-latest"]


def test_saglayici_secimi():
    from sonda.model import gemini_saglayici
    assert model._saglayici("gemini:x") is gemini_saglayici
    assert model._saglayici("qwen3.6:35b-a3b") is ollama_saglayici


def _mesaj(content="", thinking=None, tool_calls=None):
    return NS(message=NS(content=content, thinking=thinking, tool_calls=tool_calls))


def test_ollama_duz_yanit(monkeypatch):
    gelen = {}
    monkeypatch.setattr(ollama_saglayici._istemci, "chat", lambda **k: gelen.update(k) or _mesaj('{"a": 1}'))
    y = ollama_saglayici.sohbet("q", [{"role": "user", "content": "x"}], json=True, secenekler={"temperature": 0})
    assert y.metin == '{"a": 1}' and y.arac_cagrilari == []
    assert gelen["format"] == "json" and gelen["think"] is False and gelen["options"] == {"temperature": 0}
    assert gelen["stream"] is False and gelen["tools"] is None


def test_ollama_akis_ve_arac_cagrisi(monkeypatch):
    cagri = NS(function=NS(name="web_ara", arguments={"sorgular": ["a"]}))
    parcalar = [_mesaj(thinking="hmm"), _mesaj("Mer"), _mesaj("haba", tool_calls=[cagri])]
    monkeypatch.setattr(ollama_saglayici._istemci, "chat", lambda **k: iter(parcalar))
    sonuc = list(ollama_saglayici.sohbet("q", [], akis=True, dusun=True, araclar=[{"x": 1}]))
    assert [p.dusunce for p in sonuc] == ["hmm", "", ""]
    assert "".join(p.metin for p in sonuc) == "Merhaba"
    assert sonuc[2].arac_cagrilari == [model.AracCagrisi("web_ara", {"sorgular": ["a"]})]


def test_ollama_mesajlarindan_imza_temizlenir(monkeypatch):
    """Ollama ortak biçimdeki 'imza' alanını tanımaz; gönderilmeden çıkarılır."""
    gelen = {}
    monkeypatch.setattr(ollama_saglayici._istemci, "chat", lambda **k: gelen.update(k) or _mesaj("x"))
    ollama_saglayici.sohbet("q", [{"role": "assistant", "content": "", "tool_calls": [
        {"function": {"name": "f", "arguments": {}}, "imza": b"s"}]}])
    assert gelen["messages"][0]["tool_calls"] == [{"function": {"name": "f", "arguments": {}}}]


def test_ollama_zaman_siniri():
    assert ollama_saglayici._istemci._client.timeout.read == ollama_saglayici.ZAMAN_ASIMI


def test_ollama_embed_list_ps_zaman_sinirli_istemciye_bagli():
    import ollama
    assert ollama.embed.__self__ is ollama_saglayici._istemci
    assert ollama.list.__self__ is ollama_saglayici._istemci
```

- [ ] **Step 2: Testlerin başarısız olduğunu gör**

Run: `.venv/Scripts/python -m pytest tests/test_model.py -q`
Expected: FAIL — `ImportError: cannot import name 'model' from 'sonda'`

- [ ] **Step 3: Paketi yaz**

`sonda/model/__init__.py`:

```python
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
```

Task 1'de `gemini_saglayici` henüz yok; `test_saglayici_secimi` Task 2'de geçer. Task 1'de bu testi geçici olarak şu boş modülle geçir — `sonda/model/gemini_saglayici.py`:

```python
"""Google Gemini sağlayıcısı (Task 2'de doldurulur)."""


def sohbet(model, mesajlar, **k):
    raise NotImplementedError
```

`sonda/model/ollama_saglayici.py`:

```python
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
```

- [ ] **Step 4: Çağıranları taşı**

Ad çakışmasını önlemek için (fonksiyon parametreleri `model` adını kullanıyor) paket her yerde `from .. import model as saglayici` ile alınır.

`sonda/ortak.py` — `import ollama` ve istemci satırlarını (`OLLAMA_ZAMAN_ASIMI`, `_istemci`, `ollama.chat, ... =`) sil; yerine:

```python
from . import model as saglayici
```

ve `json_sor` gövdesini:

```python
def json_sor(model, sistem, kullanici=None):
    mesajlar = [{"role": "system", "content": sistem}]
    if kullanici:
        mesajlar.append({"role": "user", "content": kullanici})
    yanit = saglayici.sohbet(model, mesajlar, json=True, secenekler=JSON_SECENEKLERI)
    try:
        veri = json.loads(yanit.metin)
        return veri if isinstance(veri, dict) else {}
    except json.JSONDecodeError:
        return {}
```

`# Tüm çağrılarda aynı bağlam boyutu...` yorumu `SECENEKLER`'in üstünde kalsın; zaman sınırı yorumu sağlayıcıya taşındı.

`sonda/arastirma/sohbet.py` — `import ollama` → `from .. import model as saglayici`; döngü:

```python
    for parca in saglayici.sohbet(model, mesajlar, akis=True, secenekler=SECENEKLER):
        if parca.metin:
            cevap += parca.metin
            yield {"tur": "token", "metin": parca.metin}
```

`sonda/arastirma/derin.py` — `import ollama` → `from .. import model as saglayici`; rapor akışı:

```python
    akis = saglayici.sohbet(model, [{"role": "system", "content": sistem}, *gecmis[-4:],
                                    {"role": "user", "content": soru}], akis=True, secenekler=SECENEKLER)
    rapor = ""
    for parca in akis:
        if parca.metin:
            rapor += parca.metin
            yield {"tur": "token", "metin": parca.metin}
```

`sonda/arastirma/hizli.py` — `import ollama` → `from .. import model as saglayici`; `_dongu` gövdesi:

```python
    for tur in range(MAKS_ARAC_TURU + 1):
        son_tur = tur == MAKS_ARAC_TURU
        akis = saglayici.sohbet(model, mesajlar, akis=True, dusun=dusunme,
                                araclar=None if son_tur else ARACLAR, secenekler=SECENEKLER)
        icerik, cagrilar, dusundu = "", [], False
        for parca in akis:
            if parca.dusunce and not dusundu:
                dusundu = True
                yield {"tur": "adim", "tip": "dusun", "metin": "Adım adım akıl yürütüyor"}
            if parca.metin:
                icerik += parca.metin
                yield {"tur": "token", "metin": parca.metin}
            cagrilar.extend(parca.arac_cagrilari)
        if not cagrilar:
            yield from kaynaklar.atiflari_ekle(icerik)
            yield {"tur": "cevap_bitti", "metin": icerik}
            return
        if icerik:
            yield {"tur": "sifirla"}
        mesajlar.append({"role": "assistant", "content": icerik, "tool_calls": [
            {"function": {"name": c.ad, "arguments": c.argumanlar}, "imza": c.imza} for c in cagrilar]})
        for c in cagrilar:
            sonuc, olaylar = arac_calistir(c.ad, dict(c.argumanlar), soru, kaynaklar)
            yield from olaylar
            mesajlar.append({"role": "tool", "content": sonuc[:16000], "tool_name": c.ad})
```

`sonda/gorev/karar.py` — `import ollama` → `from .. import model as saglayici`. Üç çağrı:

```python
        yanit = saglayici.sohbet(model, [{"role": "system", "content": sistem}, mesaj], json=True, dusun=dusun,
                                 secenekler=JSON_SECENEKLERI)
        try:
            veri = json.loads(yanit.metin)
```

```python
        yanit = saglayici.sohbet(model, [
            {"role": "system", "content": DERINLIK_PROMPTU.format(tarih=bugun())},
            {"role": "user", "content": (f"Önceki konuşma:\n{onceki}\n\n" if onceki else "") + f"Görev: {gorev_metni}"}],
            json=True, secenekler=JSON_SECENEKLERI)
        veri = json.loads(yanit.metin)
```

```python
        yanit = saglayici.sohbet(model, [
            {"role": "system", "content": DEGERLENDIRME_PROMPTU.format(tarih=bugun())},
            {"role": "user", "content": icerik}], json=True, dusun=True, secenekler=JSON_SECENEKLERI)
        veri = json.loads(yanit.metin)
```

`sonda/gorev/dongu.py` — `import ollama` → `from .. import model as saglayici`; `sonuc_yaz` akışı:

```python
    for parca in saglayici.sohbet(model, [{"role": "user", "content": istem}], akis=True, dusun=dusun,
                                  secenekler=SECENEKLER):
        if parca.metin:
            cevap += parca.metin
            yield {"tur": "token", "metin": parca.metin}
```

- [ ] **Step 5: Mevcut testlerin yamalama noktalarını taşı**

`tests/test_gorev.py`:
- `class Y` tanımlarının (3 yer: `test_derinlik_cevabi_duzeltilir`, `test_derinlik_inceleme_bayragini_dondurur`, `test_ilerleme_degerlendir_cevabi_duzeltilir`) yerine modül başına ekle: `from sonda.model import Parca, Yanit` ve `Y = Yanit` kullan (`Y('{"...}')` çağrıları aynen çalışır; `Yanit` ilk argümanı `metin`).
- `monkeypatch.setattr(gorev.karar.ollama, "chat", lambda **k: Y(...))` → `monkeypatch.setattr(gorev.karar.saglayici, "sohbet", lambda *a, **k: Y(...))`.
- `test_gorulen_metin_son_cevaba_ulasir` ve `test_inceleme_sonucu_dusunerek_yazilir`: `class P` silinir; sahte:

```python
    def sahte_chat(model, mesajlar, **k):
        istemler.append(mesajlar[-1]["content"])
        return iter([Parca("ANALİZ")])
    monkeypatch.setattr(gorev.dongu.saglayici, "sohbet", sahte_chat)
```

  (ikincisinde `dusunme.append(k.get("dusun"))`).
- `test_ollama_cagrilarinin_zaman_siniri_var` silinir (yerine `tests/test_model.py::test_ollama_zaman_siniri`).

Başka dosyalarda `ollama.chat` yamalayan test kalmadığını doğrula:

Run: `grep -rn "ollama" tests/*.py`
Expected: yalnızca `tests/test_model.py` ve `tests/test_gorev_model.py` (docstring) satırları.

- [ ] **Step 6: Bütün testleri çalıştır**

Run: `.venv/Scripts/python -m pytest -q`
Expected: `test_model.py` 7 geçer; toplam 376 - 1 + 7 = 382 passed.

- [ ] **Step 7: Commit**

```bash
git add sonda/model sonda/ortak.py sonda/arastirma sonda/gorev/karar.py sonda/gorev/dongu.py tests/test_model.py tests/test_gorev.py
git commit -m "Model katmanı: bütün model çağrıları sonda.model üzerinden (Ollama sağlayıcısı)"
```

---

### Task 2: Anahtar saklama ve Gemini sağlayıcısı

**Files:**
- Create: `sonda/ayarlar.py`, `tests/test_ayarlar.py`, `tests/test_gemini.py`
- Modify: `sonda/model/gemini_saglayici.py` (Task 1'deki boş modülün yerine), `requirements.txt`

**Interfaces:**
- Consumes: `AracCagrisi`, `Parca`, `Yanit`, `ModelHatasi`, `GEMINI_ONEKI` (Task 1)
- Produces:
  - `sonda.ayarlar.DOSYA: Path`, `gemini_anahtari() -> str | None`, `gemini_kaydet(anahtar: str)`, `gemini_sil()`
  - `gemini_saglayici.sohbet(model, mesajlar, akis, json, dusun, araclar, secenekler)` (Task 1 arayüzü)
  - `gemini_saglayici.anahtar_dogrula(anahtar: str) -> None` — geçersizse `ModelHatasi`
  - `gemini_saglayici.modeller() -> list[dict]` — `[{"ad": "gemini:...", "etiket": "Gemini Flash (bulut, hızlı)"}, {"ad": "gemini:...", "etiket": "Gemini Pro (bulut, en akıllı)"}]`; anahtar yoksa `[]`
  - `gemini_saglayici.YENIDEN_DENEME_BEKLEMESI: list[float]` (testte sıfırlanır), `ZAMAN_ASIMI_MS = 120_000`, `ONBELLEK_SURESI = 3600`
  - `gemini_saglayici._istemci(anahtar) -> genai.Client` (testte yamalanır)

- [ ] **Step 1: `google-genai`'yi kur ve sabitle**

Run: `.venv/Scripts/python -m pip install google-genai==1.65.0`
Expected: `Successfully installed google-genai-1.65.0 ...`

`requirements.txt`'e `ollama==0.6.2` satırından sonra ekle: `google-genai==1.65.0`

- [ ] **Step 2: Ayarlar testlerini yaz**

`tests/test_ayarlar.py`:

```python
"""API anahtarının saklanması."""
import pytest

from sonda import ayarlar


@pytest.fixture(autouse=True)
def gecici_dosya(tmp_path, monkeypatch):
    monkeypatch.setattr(ayarlar, "DOSYA", tmp_path / "veri" / "ayarlar.json")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


def test_anahtar_yoksa_none():
    assert ayarlar.gemini_anahtari() is None


def test_kaydet_oku_sil():
    ayarlar.gemini_kaydet("  AIzaKAYITLI  ")
    assert ayarlar.gemini_anahtari() == "AIzaKAYITLI"
    ayarlar.gemini_sil()
    assert ayarlar.gemini_anahtari() is None


def test_ortam_degiskeni_yedek_kayitli_oncelikli(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "ORTAM")
    assert ayarlar.gemini_anahtari() == "ORTAM"
    ayarlar.gemini_kaydet("KAYITLI")
    assert ayarlar.gemini_anahtari() == "KAYITLI"


def test_bozuk_dosya_bos_sayilir():
    ayarlar.DOSYA.parent.mkdir(parents=True)
    ayarlar.DOSYA.write_text("{bozuk", encoding="utf-8")
    assert ayarlar.gemini_anahtari() is None
    ayarlar.gemini_kaydet("K")
    assert ayarlar.gemini_anahtari() == "K"
```

- [ ] **Step 3: Başarısız olduğunu gör**

Run: `.venv/Scripts/python -m pytest tests/test_ayarlar.py -q`
Expected: FAIL — `ImportError: cannot import name 'ayarlar'`

- [ ] **Step 4: `sonda/ayarlar.py`'yi yaz**

```python
"""Kullanıcı ayarları (veri/ayarlar.json). Dosya bu bilgisayardan çıkmaz, repoya girmez (veri/ .gitignore'da)."""
import json
import os
import threading
from pathlib import Path

DOSYA = Path(__file__).resolve().parent.parent / "veri" / "ayarlar.json"
_kilit = threading.Lock()


def _yukle():
    try:
        veri = json.loads(DOSYA.read_text(encoding="utf-8"))
        return veri if isinstance(veri, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _yaz(veri):
    DOSYA.parent.mkdir(parents=True, exist_ok=True)
    DOSYA.write_text(json.dumps(veri, ensure_ascii=False, indent=1), encoding="utf-8")


def gemini_anahtari():
    """Arayüzden kaydedilen anahtar önceliklidir; yoksa GEMINI_API_KEY."""
    return _yukle().get("gemini_anahtari") or os.environ.get("GEMINI_API_KEY") or None


def gemini_kaydet(anahtar):
    with _kilit:
        veri = _yukle()
        veri["gemini_anahtari"] = anahtar.strip()
        _yaz(veri)


def gemini_sil():
    with _kilit:
        veri = _yukle()
        veri.pop("gemini_anahtari", None)
        _yaz(veri)
```

Run: `.venv/Scripts/python -m pytest tests/test_ayarlar.py -q` → Expected: 4 passed

- [ ] **Step 5: Gemini sağlayıcı testlerini yaz**

Sahte istemci, `google.genai.types` nesnelerini alır; yanıtlar gerçek `types.GenerateContentResponse` ile kurulur ki dönüşüm gerçek tiplere karşı sınansın.

`tests/test_gemini.py`:

```python
"""Gemini sağlayıcısı: sahte istemciyle dönüşüm, akış, araçlar, hata çevirisi."""
from types import SimpleNamespace as NS

import httpx
import pytest
from google.genai import errors, types

from sonda import ayarlar, model
from sonda.model import AracCagrisi, ModelHatasi, gemini_saglayici as gs

ANAHTAR = "AIzaSyTESTANAHTAR0123456789abcdefghijklm"


def yanit(*parcalar, bitis="STOP", engel=None):
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=list(parcalar)), finish_reason=bitis)],
        prompt_feedback=types.GenerateContentResponsePromptFeedback(block_reason=engel) if engel else None)


def api_hatasi(kod, mesaj="x"):
    sinif = errors.ClientError if kod < 500 else errors.ServerError
    return sinif(kod, {"error": {"code": kod, "message": mesaj, "status": "S"}})


class SahteModeller:
    def __init__(self, cevaplar):
        self.cevaplar, self.cagrilar = list(cevaplar), []

    def _sonraki(self, k):
        self.cagrilar.append(k)
        c = self.cevaplar.pop(0)
        if isinstance(c, Exception):
            raise c
        return c

    def generate_content(self, **k):
        return self._sonraki(k)

    def generate_content_stream(self, **k):
        c = self._sonraki(k)
        return iter(c)

    def list(self, **k):
        return self._sonraki(k)


@pytest.fixture
def sahte(monkeypatch, tmp_path):
    monkeypatch.setattr(ayarlar, "DOSYA", tmp_path / "ayarlar.json")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    ayarlar.gemini_kaydet(ANAHTAR)
    monkeypatch.setattr(gs, "YENIDEN_DENEME_BEKLEMESI", [0, 0, 0])
    gs._model_onbellegi.clear()

    def kur(*cevaplar):
        m = SahteModeller(cevaplar)
        monkeypatch.setattr(gs, "_istemci", lambda anahtar: NS(models=m))
        return m
    return kur


def test_sistem_rol_ve_gorsel_donusumu(sahte):
    m = sahte(yanit(types.Part(text="tamam")))
    y = gs.sohbet("gemini:gemini-flash-latest", [
        {"role": "system", "content": "SİSTEM"},
        {"role": "user", "content": "soru", "images": [b"\xff\xd8jpeg"]},
        {"role": "assistant", "content": "önceki"},
        {"role": "user", "content": "yeni"}])
    assert y.metin == "tamam"
    k = m.cagrilar[0]
    assert k["model"] == "gemini-flash-latest"
    assert k["config"].system_instruction == "SİSTEM"
    assert [c.role for c in k["contents"]] == ["user", "model", "user"]
    ilk = k["contents"][0].parts
    assert ilk[0].text == "soru" and ilk[1].inline_data.mime_type == "image/jpeg" and ilk[1].inline_data.data == b"\xff\xd8jpeg"


def test_json_modu_ve_sicaklik(sahte):
    m = sahte(yanit(types.Part(text='{"a": 1}')))
    gs.sohbet("gemini:g", [{"role": "user", "content": "x"}], json=True, secenekler={"num_ctx": 32768, "temperature": 0})
    c = m.cagrilar[0]["config"]
    assert c.response_mime_type == "application/json" and c.temperature == 0


def test_dusunme_ayari(sahte):
    m = sahte(yanit(types.Part(text="a")), yanit(types.Part(text="b")))
    gs.sohbet("gemini:g", [{"role": "user", "content": "x"}], dusun=False)
    gs.sohbet("gemini:g", [{"role": "user", "content": "x"}], dusun=True)
    kapali, acik = (c["config"].thinking_config for c in m.cagrilar)
    assert kapali.include_thoughts is not True and kapali.thinking_level == types.ThinkingLevel.LOW
    assert acik.include_thoughts is True and acik.thinking_level == types.ThinkingLevel.HIGH


def test_dusunme_ayarini_desteklemeyen_model_ayarsiz_denenir(sahte):
    m = sahte(api_hatasi(400, "Thinking level is not supported for this model."), yanit(types.Part(text="ok")))
    assert gs.sohbet("gemini:gemini-2.0-flash", [{"role": "user", "content": "x"}]).metin == "ok"
    assert m.cagrilar[1]["config"].thinking_config is None


def test_akis_parcalari(sahte):
    sahte([yanit(types.Part(text="düşünüyorum", thought=True)), yanit(types.Part(text="Mer")),
           yanit(types.Part(text="haba"))])
    p = list(gs.sohbet("gemini:g", [{"role": "user", "content": "x"}], akis=True, dusun=True))
    assert [x.dusunce for x in p] == ["düşünüyorum", "", ""]
    assert "".join(x.metin for x in p) == "Merhaba"


def test_arac_tanimi_ve_cagrisi(sahte):
    from sonda.arastirma.araclar import ARACLAR
    cagri = types.Part(function_call=types.FunctionCall(name="web_ara", args={"sorgular": ["a"]}),
                       thought_signature=b"IMZA")
    m = sahte([yanit(cagri)])
    p = list(gs.sohbet("gemini:g", [{"role": "user", "content": "x"}], akis=True, araclar=ARACLAR))
    assert p[0].arac_cagrilari == [AracCagrisi("web_ara", {"sorgular": ["a"]}, b"IMZA")]
    bildirimler = m.cagrilar[0]["config"].tools[0].function_declarations
    assert [b.name for b in bildirimler] == [a["function"]["name"] for a in ARACLAR]
    assert bildirimler[0].parameters_json_schema == ARACLAR[0]["function"]["parameters"]


def test_arac_cagrisi_ve_cevabi_gidis_donus(sahte):
    m = sahte(yanit(types.Part(text="cevap")))
    gs.sohbet("gemini:g", [
        {"role": "user", "content": "soru"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "web_ara", "arguments": {"sorgular": ["a"]}}, "imza": b"IMZA"},
            {"function": {"name": "hesapla", "arguments": {"ifade": "1+1"}}, "imza": None}]},
        {"role": "tool", "content": "sonuçlar", "tool_name": "web_ara"},
        {"role": "tool", "content": "2", "tool_name": "hesapla"}])
    icerik = m.cagrilar[0]["contents"]
    assert [c.role for c in icerik] == ["user", "model", "user"]
    fc = icerik[1].parts
    assert fc[0].function_call.name == "web_ara" and fc[0].thought_signature == b"IMZA"
    fr = icerik[2].parts  # ardışık araç cevapları tek içerikte toplanır
    assert [x.function_response.name for x in fr] == ["web_ara", "hesapla"]
    assert fr[0].function_response.response == {"sonuc": "sonuçlar"}


def test_imzasiz_arac_cagrisina_atlama_imzasi_konur(sahte):
    """Hızlı mod ilk aramayı modelsiz yapıp çağrı olarak ekler; Gemini 3 imzasız çağrıyı reddeder."""
    m = sahte(yanit(types.Part(text="x")))
    gs.sohbet("gemini:g", [{"role": "user", "content": "s"},
                           {"role": "assistant", "content": "", "tool_calls": [
                               {"function": {"name": "web_ara", "arguments": {}}}]},
                           {"role": "tool", "content": "r", "tool_name": "web_ara"}])
    assert m.cagrilar[0]["contents"][1].parts[0].thought_signature == b"skip_thought_signature_validator"


@pytest.mark.parametrize("hata,mesaj", [
    (api_hatasi(400, "API key not valid. Please pass a valid API key."), "Gemini anahtarı geçersiz ya da yetkisiz. Ayarlar'dan kontrol et."),
    (api_hatasi(403, "Permission denied"), "Gemini anahtarı geçersiz ya da yetkisiz. Ayarlar'dan kontrol et."),
    (httpx.ConnectError("getaddrinfo failed"), "Gemini'ye ulaşılamadı (internet bağlantısı?)."),
])
def test_hata_cevirisi(sahte, hata, mesaj):
    sahte(hata)
    with pytest.raises(ModelHatasi) as h:
        gs.sohbet("gemini:g", [{"role": "user", "content": "x"}])
    assert str(h.value) == mesaj


def test_429_yeniden_denenir_sonra_kota_mesaji(sahte):
    m = sahte(api_hatasi(429), api_hatasi(429), yanit(types.Part(text="oldu")))
    assert gs.sohbet("gemini:g", [{"role": "user", "content": "x"}]).metin == "oldu"
    sahte(*[api_hatasi(429)] * 4)
    with pytest.raises(ModelHatasi, match="istek sınırı/kotası doldu"):
        gs.sohbet("gemini:g", [{"role": "user", "content": "x"}])


def test_5xx_yeniden_denenir_sonra_mesaj(sahte):
    sahte(*[api_hatasi(503)] * 4)
    with pytest.raises(ModelHatasi, match="Gemini şu an yanıt vermiyor."):
        gs.sohbet("gemini:g", [{"role": "user", "content": "x"}])


def test_akis_ilk_parcadan_sonra_yeniden_denenmez(sahte):
    def akis():
        yield yanit(types.Part(text="yarım"))
        raise api_hatasi(503)
    m = sahte(akis())
    uretec = gs.sohbet("gemini:g", [{"role": "user", "content": "x"}], akis=True)
    assert next(uretec).metin == "yarım"
    with pytest.raises(ModelHatasi, match="yanıt vermiyor"):
        next(uretec)
    assert len(m.cagrilar) == 1


def test_guvenlik_filtresi(sahte):
    sahte(yanit(engel="SAFETY"))
    with pytest.raises(ModelHatasi, match="güvenlik filtresi"):
        gs.sohbet("gemini:g", [{"role": "user", "content": "x"}])
    sahte(yanit(bitis="SAFETY"))
    with pytest.raises(ModelHatasi, match="güvenlik filtresi"):
        gs.sohbet("gemini:g", [{"role": "user", "content": "x"}])


def test_anahtar_yoksa_anlasilir_hata(sahte):
    ayarlar.gemini_sil()
    with pytest.raises(ModelHatasi, match="anahtarı"):
        gs.sohbet("gemini:g", [{"role": "user", "content": "x"}])


def test_anahtar_hata_metinlerinden_temizlenir(sahte):
    sahte(api_hatasi(400, f"Bad request for key={ANAHTAR} and AIzaSyBASKAANAHTAR0123456789abcdefghijk"))
    with pytest.raises(ModelHatasi) as h:
        gs.sohbet("gemini:g", [{"role": "user", "content": "x"}])
    assert ANAHTAR not in str(h.value) and "AIza" not in str(h.value)


def _model(ad, eylemler=("generateContent",)):
    return types.Model(name=f"models/{ad}", supported_actions=list(eylemler))


def test_modeller_takma_adlari_tercih_eder(sahte):
    sahte([_model("gemini-2.5-flash"), _model("gemini-flash-latest"), _model("gemini-pro-latest")])
    assert gs.modeller() == [{"ad": "gemini:gemini-flash-latest", "etiket": "Gemini Flash (bulut, hızlı)"},
                             {"ad": "gemini:gemini-pro-latest", "etiket": "Gemini Pro (bulut, en akıllı)"}]


def test_modeller_takma_ad_yoksa_en_yeni_surum(sahte):
    sahte([_model("gemini-2.5-flash"), _model("gemini-3.1-flash"), _model("gemini-3.1-flash-lite"),
           _model("gemini-3-pro"), _model("gemini-2.5-pro"), _model("gemini-9-pro", ("embedContent",))])
    assert [m["ad"] for m in gs.modeller()] == ["gemini:gemini-3.1-flash", "gemini:gemini-3-pro"]


def test_modeller_liste_alinamazsa_takma_adlar_ve_onbellek(sahte):
    m = sahte(httpx.ConnectError("yok"))
    assert [x["ad"] for x in gs.modeller()] == ["gemini:gemini-flash-latest", "gemini:gemini-pro-latest"]
    m2 = sahte([_model("gemini-flash-latest"), _model("gemini-pro-latest")])
    gs.modeller()
    gs.modeller()
    assert len(m2.cagrilar) == 1  # 1 saat önbellek


def test_anahtar_yoksa_model_listelenmez(sahte):
    ayarlar.gemini_sil()
    assert gs.modeller() == []


def test_anahtar_dogrula(sahte):
    sahte([_model("gemini-flash-latest")])
    gs.anahtar_dogrula("YENI")  # hata vermez
    sahte(api_hatasi(400, "API key not valid"))
    with pytest.raises(ModelHatasi, match="geçersiz"):
        gs.anahtar_dogrula("YANLIS")


def test_yonlendirme_gemini_saglayicisina_gider(sahte):
    sahte(yanit(types.Part(text="yönlendi")))
    assert model.sohbet("gemini:gemini-flash-latest", [{"role": "user", "content": "x"}]).metin == "yönlendi"
```

- [ ] **Step 6: Başarısız olduğunu gör**

Run: `.venv/Scripts/python -m pytest tests/test_gemini.py -q`
Expected: FAIL — `AttributeError: module 'sonda.model.gemini_saglayici' has no attribute 'YENIDEN_DENEME_BEKLEMESI'`

- [ ] **Step 7: `sonda/model/gemini_saglayici.py`'yi yaz**

```python
"""Google Gemini sağlayıcısı (resmi google-genai kütüphanesi).

Ortak (Ollama) mesaj biçimini Gemini'ye çevirir; hataları kullanıcıya gösterilecek Türkçe ModelHatasi'na
dönüştürür. Anahtar hiçbir mesajda görünmez. Hata olursa sessizce yerel modele geçilmez."""
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
TAKMA_ADLAR = {"flash": "gemini-flash-latest", "pro": "gemini-pro-latest"}
ETIKETLER = {"flash": "Gemini Flash (bulut, hızlı)", "pro": "Gemini Pro (bulut, en akıllı)"}
# Orkestratörün modelsiz eklediği araç çağrılarında düşünce imzası yoktur; Google'ın belgelediği atlama değeri
ATLAMA_IMZASI = b"skip_thought_signature_validator"

GECERSIZ = "Gemini anahtarı geçersiz ya da yetkisiz. Ayarlar'dan kontrol et."
KOTA = "Gemini istek sınırı/kotası doldu; biraz bekle ya da yerel modele geç."
SUNUCU = "Gemini şu an yanıt vermiyor."
AG = "Gemini'ye ulaşılamadı (internet bağlantısı?)."
GUVENLIK = "Gemini bu içeriği yanıtlamadı (güvenlik filtresi)."
ANAHTAR_YOK = "Gemini anahtarı kayıtlı değil. Ayarlar'dan ekle ya da yerel bir model seç."

_ANAHTAR_KALIBI = re.compile(r"AIza[0-9A-Za-z_\-]{20,}")
_model_onbellegi = {}


def _istemci(anahtar):
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


def _guvenlik_kontrolu(yanit):
    if yanit.prompt_feedback and yanit.prompt_feedback.block_reason:
        raise ModelHatasi(GUVENLIK)
    aday = (yanit.candidates or [None])[0]
    if aday and str(aday.finish_reason or "").split(".")[-1] in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII"):
        raise ModelHatasi(GUVENLIK)


def _parca(yanit):
    _guvenlik_kontrolu(yanit)
    metin, dusunce, cagrilar = "", "", []
    aday = (yanit.candidates or [None])[0]
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
            if dusunme_ayari and _dusunme_desteklenmiyor(h):
                dusunme_ayari = False
                try:
                    return islem(False)
                except Exception as h2:
                    h = h2
            tekrar, hata = _cevir(h, anahtar)
            if not tekrar or deneme == len(YENIDEN_DENEME_BEKLEMESI):
                raise hata from None
            time.sleep(YENIDEN_DENEME_BEKLEMESI[deneme])


# ---- ortak arayüz

def sohbet(model, mesajlar, akis=False, json=False, dusun=False, araclar=None, secenekler=None):
    anahtar = _anahtar()
    ad = model.removeprefix(GEMINI_ONEKI)
    sistem, icerikler = _icerikler(mesajlar)
    modeller = _istemci(anahtar).models

    if not akis:
        def islem(dusunme_ayari):
            y = modeller.generate_content(model=ad, contents=icerikler,
                                          config=_ayar(sistem, json, dusun, araclar, secenekler, dusunme_ayari))
            p = _parca(y)
            return Yanit(p.metin, p.arac_cagrilari)
        return _dene(islem, anahtar)

    def akis_uret():
        # Yeniden deneme yalnızca akış başlamadan: ilk parça geldikten sonra hata doğrudan yükselir
        def baslat(dusunme_ayari):
            it = iter(modeller.generate_content_stream(
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
    m = re.fullmatch(r"gemini-(\d+(?:\.\d+)?)-(flash|pro)", ad)
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
    """Anahtar varsa Flash ve Pro seçenekleri. Liste 1 saat önbellekte; alınamazsa takma adlar gösterilir."""
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
    return [{"ad": GEMINI_ONEKI + kayit[1][tur], "etiket": ETIKETLER[tur]} for tur in ("flash", "pro")]
```

Not: `test_modeller_liste_alinamazsa_takma_adlar_ve_onbellek` başarısız listeyi önbelleğe almadığımızı, başarılıyı aldığımızı sınar.

- [ ] **Step 8: Testleri çalıştır, geçene kadar düzelt**

Run: `.venv/Scripts/python -m pytest tests/test_gemini.py tests/test_model.py tests/test_ayarlar.py -q`
Expected: hepsi geçer. `types` nesnelerinin alan adları (ör. `parameters_json_schema`, `thinking_level`, `supported_actions`) kurulu 1.65.0 sürümünde farklıysa `python -c "from google.genai import types; help(types.X)"` ile doğrula ve hem kodu hem testi gerçek adlara uydur.

- [ ] **Step 9: Tüm paket**

Run: `.venv/Scripts/python -m pytest -q`
Expected: hepsi geçer.

- [ ] **Step 10: Commit**

```bash
git add sonda/ayarlar.py sonda/model/gemini_saglayici.py tests/test_ayarlar.py tests/test_gemini.py requirements.txt
git commit -m "Gemini sağlayıcısı: mesaj/araç/görsel dönüşümü, yeniden deneme, Türkçe hata; anahtar saklama"
```

---

### Task 3: Sunucu uç noktaları, model listesi ve ModelHatasi'nın kullanıcıya ulaşması

**Files:**
- Modify: `sonda/sunucu.py`, `sonda/asistan.py`, `sonda/yonlendirme.py`, `sonda/gorev/dongu.py`, `tests/test_sunucu.py`, `tests/test_gorev.py`

**Interfaces:**
- Consumes: `ayarlar.gemini_anahtari/gemini_kaydet/gemini_sil`, `gemini_saglayici.modeller/anahtar_dogrula`, `ModelHatasi` (Task 1-2)
- Produces:
  - `GET /api/ayarlar` → `{"gemini": {"var": bool, "son4": "…abcd" | ""}}`
  - `POST /api/ayarlar/gemini {"anahtar": str}` → `{"tamam": true, "son4": "…abcd"}` ya da 400 `{"detail": "<Türkçe mesaj>"}`
  - `DELETE /api/ayarlar/gemini` → `{"tamam": true}`
  - `GET /api/modeller` → yerel modeller + Gemini modelleri
  - `hata` olayı: `ModelHatasi` için `{"tur": "hata", "metin": "<Türkçe mesaj>", "bulut": true}`; diğer hatalar eskisi gibi `"Tip: mesaj"`
  - Görev: `ModelHatasi` → `gorev_bitti` `durum: "hata"`; cevap modelsiz (hata + notlar)
  - `dongu.duz_sonuc(durum) -> str` (modelsiz sonuç metni)

- [ ] **Step 1: Sunucu testlerini yaz**

`tests/test_sunucu.py` sonuna ekle:

```python
# ---- Gemini: ayarlar ve model listesi
from sonda import ayarlar
from sonda.model import ModelHatasi, gemini_saglayici


@pytest.fixture
def gecici_ayar(tmp_path, monkeypatch):
    monkeypatch.setattr(ayarlar, "DOSYA", tmp_path / "ayarlar.json")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


def test_ayarlar_anahtarin_tamamini_dondurmez(gecici_ayar, monkeypatch):
    assert istemci.get("/api/ayarlar").json() == {"gemini": {"var": False, "son4": ""}}
    monkeypatch.setattr(gemini_saglayici, "anahtar_dogrula", lambda a: None)
    r = istemci.post("/api/ayarlar/gemini", json={"anahtar": "AIzaGIZLIGIZLIabcd"})
    assert r.json() == {"tamam": True, "son4": "…abcd"}
    govde = istemci.get("/api/ayarlar").text
    assert "GIZLI" not in govde and '"son4":"…abcd"' in govde.replace(" ", "")
    assert istemci.delete("/api/ayarlar/gemini").json() == {"tamam": True}
    assert ayarlar.gemini_anahtari() is None


def test_gecersiz_anahtar_kaydedilmez(gecici_ayar, monkeypatch):
    def red(a):
        raise ModelHatasi("Gemini anahtarı geçersiz ya da yetkisiz. Ayarlar'dan kontrol et.")
    monkeypatch.setattr(gemini_saglayici, "anahtar_dogrula", red)
    r = istemci.post("/api/ayarlar/gemini", json={"anahtar": "YANLIS"})
    assert r.status_code == 400 and "geçersiz" in r.json()["detail"] and "YANLIS" not in r.text
    assert ayarlar.gemini_anahtari() is None


def test_bos_anahtar_reddedilir(gecici_ayar):
    assert istemci.post("/api/ayarlar/gemini", json={"anahtar": "  "}).status_code == 400


def test_modeller_gemini_ekler(monkeypatch):
    monkeypatch.setattr(sunucu.ollama, "list", lambda: type("L", (), {"models": [type("M", (), {"model": "qwen2.5:7b"})()]})())
    monkeypatch.setattr(gemini_saglayici, "modeller", lambda: [{"ad": "gemini:gemini-flash-latest", "etiket": "Gemini Flash (bulut, hızlı)"}])
    assert [m["ad"] for m in istemci.get("/api/modeller").json()] == ["qwen2.5:7b", "gemini:gemini-flash-latest"]


def test_ollama_kapaliyken_gemini_yine_listelenir(monkeypatch):
    monkeypatch.setattr(sunucu.ollama, "list", lambda: (_ for _ in ()).throw(ConnectionError()))
    monkeypatch.setattr(gemini_saglayici, "modeller", lambda: [{"ad": "gemini:x", "etiket": "E"}])
    assert [m["ad"] for m in istemci.get("/api/modeller").json()] == ["gemini:x"]


def test_model_hatasi_turkce_mesajla_akar(monkeypatch):
    def patla(*a, **k):
        raise ModelHatasi("Gemini şu an yanıt vermiyor.")
        yield
    monkeypatch.setattr(asistan, "hizli", patla)
    monkeypatch.setattr(asistan, "hafizayi_guncelle", lambda *a: None)
    olaylar = list(asistan.calistir("soru", [], "gemini:x", "hizli"))
    assert olaylar[-1] == {"tur": "hata", "metin": "Gemini şu an yanıt vermiyor.", "bulut": True}


def test_oneri_uretirken_model_hatasi_sessiz(monkeypatch):
    monkeypatch.setattr(asistan, "hizli", lambda *a, **k: iter([{"tur": "cevap_bitti", "metin": "x" * 100}]))
    monkeypatch.setattr(asistan, "hafizayi_guncelle", lambda *a: None)
    monkeypatch.setattr(asistan, "json_sor", lambda *a: (_ for _ in ()).throw(ModelHatasi("kota")))
    assert [o["tur"] for o in asistan.calistir("s", [], "gemini:x", "hizli")] == ["bitti"]


def test_yonlendirme_model_hatasini_yutmaz(monkeypatch):
    monkeypatch.setattr(yonlendirme, "json_sor", lambda *a: (_ for _ in ()).throw(ModelHatasi("kota")))
    with pytest.raises(ModelHatasi):
        yonlendirme.yon_belirle("m", "x", [])
```

Dosyanın başında `import pytest` ve `from sonda import yonlendirme` yoksa ekle.

- [ ] **Step 2: Başarısız olduğunu gör**

Run: `.venv/Scripts/python -m pytest tests/test_sunucu.py -q`
Expected: FAIL — `/api/ayarlar` 404, `bulut` anahtarı yok vb.

- [ ] **Step 3: `sonda/sunucu.py`**

İçe aktarmaya ekle: `from . import ayarlar, gorev, hafiza` ve `from .model import ModelHatasi, gemini_saglayici`.

`modeller()`:

```python
@app.get("/api/modeller")
def modeller():
    try:
        kurulu = {m.model for m in ollama.list().models}
    except Exception:
        kurulu = set()
    yerel = [{"ad": ad, "etiket": ETIKETLER[ad]} for ad in TERCIH_SIRASI if ad in kurulu]
    return yerel + gemini_saglayici.modeller()
```

Ayarlar uç noktaları (`/api/durum`'un üstüne):

```python
def _son4(anahtar):
    return f"…{anahtar[-4:]}" if anahtar else ""


@app.get("/api/ayarlar")
def ayar_durumu():
    anahtar = ayarlar.gemini_anahtari()
    return {"gemini": {"var": bool(anahtar), "son4": _son4(anahtar)}}


class AnahtarIstegi(BaseModel):
    anahtar: str


@app.post("/api/ayarlar/gemini")
def gemini_kaydet(istek: AnahtarIstegi):
    anahtar = istek.anahtar.strip()
    if not anahtar:
        raise HTTPException(400, "Anahtar boş olamaz.")
    try:
        gemini_saglayici.anahtar_dogrula(anahtar)
    except ModelHatasi as h:
        raise HTTPException(400, str(h))
    ayarlar.gemini_kaydet(anahtar)
    gemini_saglayici._model_onbellegi.clear()
    return {"tamam": True, "son4": _son4(anahtar)}


@app.delete("/api/ayarlar/gemini")
def gemini_sil():
    ayarlar.gemini_sil()
    return {"tamam": True}
```

- [ ] **Step 4: `sonda/asistan.py`**

İçe aktar: `from .model import ModelHatasi`. `oneriler` fonksiyonunda `json_sor` çağrısını sar:

```python
    try:
        veri = json_sor(model, ONERI_PROMPTU.format(soru=soru, cevap=cevap[:3000]))
    except ModelHatasi:
        return  # cevap zaten verildi; öneri eksikliği hata sayılmaz
```

`calistir` içindeki `except Exception as e:` bloğunun önüne:

```python
    except ModelHatasi as e:
        yield {"tur": "hata", "metin": str(e), "bulut": True}
```

- [ ] **Step 5: `sonda/yonlendirme.py`**

```python
from .model import ModelHatasi
...
    try:
        veri = json_sor(...)
    except ModelHatasi:
        raise  # anahtar/kota sorunu: görev açılıp tarayıcı boşuna başlatılmasın, kullanıcı hemen görsün
    except Exception:
        return "gorev"
```

- [ ] **Step 6: Görev testlerini yaz**

`tests/test_gorev.py` sonuna:

```python
# ---- Gemini: görev sırasında model hatası notları kaybettirmez
def test_gorevde_model_hatasi_notlari_korur(sahte, yerel_tarayici_ac, site):
    from sonda.model import ModelHatasi
    m = sahte([{"eylem": "git", "url": f"{site}/giris.html"}, {"eylem": "not_al", "metin": "Giriş formu var"}])
    asil = m.__call__

    def kota(model, istem, ekran=None, dusun=False):
        if len(m.istemler) == 2:
            raise ModelHatasi("Gemini istek sınırı/kotası doldu; biraz bekle ya da yerel modele geç.")
        return asil(model, istem, ekran, dusun)
    gorev.karar.karar_al = kota
    gorev.dongu.sonuc_yaz = ORIJINAL_SONUC_YAZ  # sahte fikstürü değiştirmişti; modelsiz yol gerçek fonksiyonda
    o = calistir(yerel_tarayici_ac)
    assert {"tur": "gorev_bitti", "durum": "hata"} in o
    cevap = "".join(x["metin"] for x in o if x["tur"] == "token")
    assert "kotası doldu" in cevap and "Giriş formu var" in cevap
    assert not any(x["tur"] == "hata" for x in o)


def test_sonuc_yazarken_model_hatasi(monkeypatch):
    from sonda.gorev.sayfa import SayfaHafizasi
    from sonda.model import ModelHatasi

    def patla(*a, **k):
        raise ModelHatasi("Gemini şu an yanıt vermiyor.")
    monkeypatch.setattr(gorev.dongu.saglayici, "sohbet", patla)
    durum = {"notlar": [{"metin": "SSD 2.649 TL", "url": "https://a.com/x", "baslik": "A"}], "adimlar": [],
             "hafiza": SayfaHafizasi(), "sonuc": "", "hal": "Görev tamamlandı.", "gizli": set()}
    o = list(ORIJINAL_SONUC_YAZ("m", "ssd bul", durum))
    metin = "".join(x["metin"] for x in o if x["tur"] == "token")
    assert "yanıt vermiyor" in metin and "SSD 2.649 TL [1]" in metin
    assert o[-1]["tur"] == "cevap_bitti"
```

Not: `sahte` fikstürü `monkeypatch` ile `sonuc_yaz`'ı yamaladığı için ilk testteki doğrudan atama test sonunda `monkeypatch` tarafından geri alınmaz. Bunun yerine `sahte` fikstürünün imzasına erişmek için testi `monkeypatch` alacak şekilde yaz ve `monkeypatch.setattr(gorev.dongu, "sonuc_yaz", ORIJINAL_SONUC_YAZ)` kullan; `gorev.karar.karar_al = kota` ataması da `monkeypatch.setattr(gorev.karar, "karar_al", kota)` olsun.

- [ ] **Step 7: Başarısız olduğunu gör**

Run: `.venv/Scripts/python -m pytest tests/test_gorev.py -q -k "model_hatasi"`
Expected: FAIL — görev `hata` olayıyla biter, `gorev_bitti` yok.

- [ ] **Step 8: `sonda/gorev/dongu.py`**

İçe aktar: `from ..model import ModelHatasi`.

`yurut` içinde `dongu` çağrısını saran `try`'a:

```python
    try:
        yield from dongu(g, gorev_metni, onceki, model, t, durum, derinlik)
    except tarayici.SekmeKapandi:
        ...
    except ModelHatasi as h:
        yield adim("hata", str(h))
        durum["kod"], durum["hal"] = "hata", str(h)
    finally:
```

`derinlik_belirle` her hatayı yutar (varsayılan derinlikle sürer); değişiklik gerekmez.

`sonuc_yaz`'ı model hatasına dayanıklı yap ve modelsiz sonucu ekle:

```python
def duz_sonuc(durum):
    """Model kullanılamadığında cevap: durum ve notlar düz liste (notlar kaybolmasın)."""
    satirlar = [durum["hal"]]
    if durum["notlar"]:
        satirlar.append("\nO ana kadar aldığım notlar:")
        satirlar += [f"- {n['metin']} [{i}]" for i, n in enumerate(durum["notlar"], 1)]
    return "\n".join(satirlar)
```

`sonuc_yaz` içinde kaynak olayları üretildikten sonra:

```python
    if durum.get("kod") == "hata":
        cevap = duz_sonuc(durum)
        yield {"tur": "token", "metin": cevap}
        yield {"tur": "cevap_bitti", "metin": cevap}
        return
```

ve model akışını sar:

```python
    try:
        for parca in saglayici.sohbet(...):
            ...
    except ModelHatasi as h:
        durum["hal"] = f"{durum['hal']} Sonuç yazılırken: {h}"
        ek = duz_sonuc(durum)
        if cevap:
            ek = "\n\n" + ek
        cevap += ek
        yield {"tur": "token", "metin": ek}
    yield {"tur": "cevap_bitti", "metin": cevap}
```

Kaynak numaraları `Kaynaklar.ekle` sırasıyla eşleşir (notlar sırayla eklenir, aynı URL aynı numarayı alır); `duz_sonuc` numaralandırmasını bu yüzden `sonuc_yaz`'daki `satirlar` listesinden al: `duz_sonuc(durum, satirlar)` imzasıyla `satirlar` (`"[no] metin"`) verilir ve `f"- {s}"` yazılır. Testteki beklenen biçim buna göre: `"- [1] SSD 2.649 TL"`. Testi `"[1] SSD 2.649 TL" in metin` olarak düzelt ve kodu şöyle yaz:

```python
def duz_sonuc(durum, satirlar):
    """Model kullanılamadığında cevap: durum ve numaralı notlar düz liste (notlar kaybolmasın)."""
    metin = durum["hal"]
    if satirlar:
        metin += "\n\nO ana kadar aldığım notlar:\n" + "\n".join(f"- {s}" for s in satirlar)
    return metin
```

- [ ] **Step 9: Testleri çalıştır**

Run: `.venv/Scripts/python -m pytest tests/test_sunucu.py tests/test_gorev.py -q`
Expected: hepsi geçer.

- [ ] **Step 10: Tüm paket ve commit**

Run: `.venv/Scripts/python -m pytest -q` → hepsi geçer.

```bash
git add sonda/sunucu.py sonda/asistan.py sonda/yonlendirme.py sonda/gorev/dongu.py tests/test_sunucu.py tests/test_gorev.py
git commit -m "Gemini: ayarlar uç noktaları, model listesi; model hatası kullanıcıya Türkçe, görevde notlar korunur"
```

---

### Task 4: Şifre yer tutucu — görevde verilen şifre hiçbir modele gitmez

**Files:**
- Modify: `sonda/koruma.py`, `sonda/gorev/dongu.py`, `sonda/gorev/promptlar.py`, `sonda/asistan.py`, `sonda/sunucu.py`, `tests/test_koruma.py`, `tests/test_gorev.py`, `tests/test_sunucu.py`

**Interfaces:**
- Consumes: `koruma.gizli_adaylar`, `koruma.gizle`, `koruma.kontrol` (mevcut)
- Produces:
  - `koruma.yer_tutucular(metin: str) -> dict[str, str]` — `{"{SIFRE_1}": "Parola-7788", ...}`, metindeki geçiş sırasına göre
  - `koruma.yer_tut(metin: str, harita: dict) -> str` — gerçek şifreleri yer tutucuyla değiştirir (büyük/küçük harf duyarsız)
  - `koruma.YER_TUTUCU = re.compile(r"\{SIFRE_\d+\}")`
  - `asistan.sifresiz(metin) -> str` — `koruma.gizle(metin, koruma.gizli_adaylar(metin))`

- [ ] **Step 1: Koruma birim testleri**

`tests/test_koruma.py` sonuna:

```python
def test_yer_tutucular_sirayla():
    h = koruma.yer_tutucular("upwork.com şifrem Parola-7788, gmail şifresi abc!12345 olsun")
    assert h == {"{SIFRE_1}": "Parola-7788", "{SIFRE_2}": "abc!12345"}


def test_yer_tut_metni_degistirir():
    h = {"{SIFRE_1}": "Parola-7788"}
    assert koruma.yer_tut("şifrem Parola-7788 ile gir, parola-7788", h) == "şifrem {SIFRE_1} ile gir, {SIFRE_1}"


def test_sifre_yoksa_bos_harita():
    assert koruma.yer_tutucular("en ucuz ssd'yi bul") == {}
```

(`from sonda import koruma` dosyada zaten var mı kontrol et; yoksa ekle.)

- [ ] **Step 2: Başarısız olduğunu gör**

Run: `.venv/Scripts/python -m pytest tests/test_koruma.py -q -k "yer_tut"`
Expected: FAIL — `AttributeError: ... 'yer_tutucular'`

- [ ] **Step 3: `sonda/koruma.py`'ye ekle** (`gizle`'nin altına)

```python
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
```

Run: `.venv/Scripts/python -m pytest tests/test_koruma.py -q` → hepsi geçer.

- [ ] **Step 4: Görev testlerini yaz / güncelle**

`tests/test_gorev.py` — `test_gorevde_verilen_sifre_girilir_ve_gizlenir` içindeki `akilli`, gerçek şifre yerine yer tutucu yazsın ve istemin hiçbir yerinde şifre olmasın:

```python
            return {"eylem": "yaz", "no": int(satir[1:satir.index("]")]), "metin": "{SIFRE_1}"}
    ...
    assert isinde(lambda: kayit["t"].sayfa.input_value("[name=sifre]")) == "Parola-7788"
    assert not any("Parola-7788" in str(x.get("metin", "")) for x in o)
    assert "Parola-7788" not in "\n".join(m.istemler)
    assert "{SIFRE_1}" in m.istemler[0]
```

Yeni testler (dosya sonuna):

```python
# ---- Gemini: şifre yer tutucu
SIFRELI = "{site}/giris.html sayfasında semih@ornek.com ve şifrem Parola-7788 ile giriş yap"


def _alana_yaz(m, etiket, deger):
    """İlk adımdan sonra etiketi geçen alana verilen değeri yazan sahte karar."""
    asil = m.__call__

    def akilli(model, istem, ekran=None, dusun=False):
        if len(m.istemler) == 1:
            m.istemler.append(istem)
            satir = next(x for x in istem.splitlines() if etiket in x and x.startswith("["))
            return {"eylem": "yaz", "no": int(satir[1:satir.index("]")]), "metin": deger}
        return asil(model, istem, ekran, dusun)
    return akilli


def test_model_istemlerinde_ve_derinlikte_sifre_yok(sahte, yerel_tarayici_ac, site, monkeypatch):
    m = sahte([{"eylem": "git", "url": f"{site}/giris.html"}, {"eylem": "bitir"}])
    gorulen = []
    monkeypatch.setattr(gorev.karar, "derinlik_belirle", lambda model, metin, onceki: gorulen.append(metin) or dict(DERINLIK))
    calistir(yerel_tarayici_ac, metin=SIFRELI.format(site=site))
    assert "Parola-7788" not in "\n".join(m.istemler + gorulen)
    assert "{SIFRE_1}" in gorulen[0] and "{SIFRE_1}" in m.istemler[0]


def test_yer_tutucu_baska_alana_yazilamaz(sahte, yerel_tarayici_ac, site, monkeypatch):
    kayit = {}
    m = sahte([{"eylem": "git", "url": f"{site}/giris.html"}])
    monkeypatch.setattr(gorev.karar, "karar_al", _alana_yaz(m, "posta", "{SIFRE_1}"))
    o = calistir(yerel_tarayici_ac, metin=SIFRELI.format(site=site), kayit=kayit, komutlar=["durdur"])
    deger = isinde(lambda: kayit["t"].sayfa.eval_on_selector("input:not([type=password])", "e => e.value"))
    assert "Parola-7788" not in deger
    assert any(x["tur"] == "adim" and x.get("tip") == "engel" for x in o) or "🔒" in m.istemler[2]
    isinde(kayit["t"]._kapat_asil)


def test_yer_tutucu_adrese_konamaz(sahte, yerel_tarayici_ac, site):
    m = sahte([{"eylem": "git", "url": f"{site}/giris.html"},
               {"eylem": "git", "url": "https://evil.example/?p={SIFRE_1}"}, {"eylem": "bitir"}])
    o = calistir(yerel_tarayici_ac, metin=SIFRELI.format(site=site))
    assert "evil.example" not in "".join(str(x.get("metin", "")) for x in o if x["tur"] == "adim")
    assert "🔒" in m.istemler[2].split("SON EYLEMİN SONUCU:")[1][:200]


def test_yer_tutucu_baska_sitede_yazilamaz(sahte, yerel_tarayici_ac, site, monkeypatch):
    """Görevde adı geçen site 'upwork.com'; yerel test sitesinin şifre alanına gerçek şifre yazılmaz."""
    kayit = {}
    m = sahte([{"eylem": "git", "url": f"{site}/giris.html"}])
    monkeypatch.setattr(gorev.karar, "karar_al", _alana_yaz(m, "Şifre", "{SIFRE_1}"))
    calistir(yerel_tarayici_ac, metin="upwork.com şifrem Parola-7788, önce " + f"{site}/giris.html sayfasına bak",
             kayit=kayit, komutlar=["durdur"])
    assert isinde(lambda: kayit["t"].sayfa.input_value("[name=sifre]")) == ""
    isinde(kayit["t"]._kapat_asil)
```

Not: `tests/sayfalar/giris.html`'deki alan etiketlerini (`"posta"`, `"Şifre"`) `sayfa_ozeti` çıktısıyla doğrula (`.venv/Scripts/python -c` ile ya da ilk testte `print(m.istemler[1])`); farklıysa `_alana_yaz`'a verilen etiketi gerçek satırdakiyle değiştir.

`tests/test_sunucu.py` sonuna:

```python
def test_yonlendirme_ve_gecmis_sifreyi_gormez(monkeypatch):
    gorulen = []
    monkeypatch.setattr(asistan, "hafizayi_guncelle", lambda *a: None)
    monkeypatch.setattr(asistan, "yon_belirle", lambda model, soru, gecmis: gorulen.append((soru, gecmis)) or "sohbet")
    monkeypatch.setattr(asistan, "sohbet", lambda soru, gecmis, *a: gorulen.append((soru, gecmis)) or iter([]))
    list(asistan.calistir("upwork şifrem Parola-7788 ile gir", [{"role": "user", "content": "şifrem Gizli-4455"}],
                          "gemini:x", "gorev"))
    assert "Parola-7788" not in repr(gorulen) and "Gizli-4455" not in repr(gorulen)


def test_baslik_sifreyi_gormez(monkeypatch):
    gorulen = []
    monkeypatch.setattr(sunucu, "baslik_uret", lambda model, soru: gorulen.append(soru) or "Başlık")
    istemci.post("/api/baslik", json={"soru": "upwork şifrem Parola-7788 ile gir", "model": "gemini:x"})
    assert gorulen and "Parola-7788" not in gorulen[0]
```

- [ ] **Step 5: Başarısız olduğunu gör**

Run: `.venv/Scripts/python -m pytest tests/test_gorev.py tests/test_sunucu.py -q -k "sifre or yer_tutucu"`
Expected: FAIL — istemlerde `Parola-7788` var, `{SIFRE_1}` yok.

- [ ] **Step 6: `sonda/gorev/dongu.py` — yer tutucu akışı**

`dongu()` başında, `durum["gizli"].update(...)` satırından sonra:

```python
    harita = koruma.yer_tutucular(gorev_metni)
    model_metni = koruma.yer_tut(gorev_metni, harita)  # modele giden her istem bunu kullanır
    if harita:
        model_metni += ("\n(Görevde verilen şifre " + ", ".join(harita) + " olarak gizlendi. Şifre alanına tam olarak "
                        "bu yer tutucuyu yaz; gerçek şifreyi Sonda doldurur.)")
```

Model çağrılarına `gorev_metni` yerine `model_metni` geçir:
- `kararlar.ilerleme_degerlendir(model, model_metni, derinlik, notlar, hafiza_)`
- `istem(model_metni, onceki, derinlik, ...)`

`gorev_metni` (gerçek) şu yerlerde kalır: `koruma.kontrol`, `koruma.gizli_adaylar`, `eksik_form_alanlari`, `uygula` (yalnızca yerel embedding ile sayfa parçası seçer).

`yaz`/`sec` öğe kontrolünden hemen önce (`if not sebep and e in ("tikla", "yaz", "sec"):` bloğunun başında, `bilgi = t.oge_bilgisi(no)` satırından sonra, `koruma.kontrol` çağrısından önce):

```python
            if e in ("yaz", "sec"):
                alan = "metin" if e == "yaz" else "deger"
                deger = str(karar.get(alan) or "").strip()
                if deger in harita:
                    karar[alan] = harita[deger]  # gerçek şifre yalnızca burada, koruma kontrolünden hemen önce
                elif koruma.YER_TUTUCU.search(deger):
                    geri_bildirim = "🔒 Şifre yer tutucusu yalnızca şifre alanına, tek başına yazılabilir."
                    adimlar.append(f"{adim_no}. {e} [{no}] -> yer tutucu engellendi")
                    continue
```

Gerçek değer konduktan sonra `koruma.kontrol` mevcut kurallarla karar verir: alan şifre alanı değilse `_gizli_iceriyor` engeller; site görevdekiyle eşleşmiyorsa `_kimlik_gorevi` başarısız olur ve yine engellenir.

`git` kontrolünde (`elif not sebep and e == "git":`) `koruma.kontrol`'dan önce:

```python
            if koruma.YER_TUTUCU.search(str(karar.get("url") or "")):
                geri_bildirim = "🔒 Şifre hiçbir adrese yazılamaz."
                adimlar.append(f"{adim_no}. git -> yer tutucu içeren adres engellendi")
                continue
```

`yurut()` içinde derinlik çağrısı:

```python
    derinlik = kararlar.derinlik_belirle(model, koruma.yer_tut(gorev_metni, koruma.yer_tutucular(gorev_metni)), onceki)
```

- [ ] **Step 7: `sonda/gorev/promptlar.py` — şifre kuralı**

`SISTEM` içindeki "Şifre:" maddesini şöyle değiştir:

```
- Şifre: kullanıcı görevde bir sitenin şifresini verdiyse şifre sana {{SIFRE_1}} gibi bir yer tutucuyla gösterilir.
  Giriş gerekiyorsa o sitede şifre alanına tam olarak bu yer tutucuyu yaz (gerçek şifreyi Sonda doldurur); yer
  tutucuyu başka hiçbir alana ya da adrese yazma. Görevde şifre yoksa giriş yapmaya çalışma: giriş sayfası
  çıkarsa sana_birak ile girişi kullanıcıya bırak.
```

(`SISTEM` `.format()` ile doldurulduğu için süslü parantezler iki kat yazılır; `python -c "from sonda.gorev.promptlar import SISTEM; print(SISTEM.format(tarih='x', hafiza=''))"` ile `{SIFRE_1}` çıktısını doğrula.)

- [ ] **Step 8: `sonda/asistan.py` ve `sonda/sunucu.py` — geçmiş ve başlık**

`asistan.py`:

```python
from . import gorev, hafiza, koruma
...
def sifresiz(metin):
    """Mesajda verilen şifre yönlendirme, başlık ve sohbet modellerine gitmesin (görev modu kendi yer tutucusunu kullanır)."""
    return koruma.gizle(metin, koruma.gizli_adaylar(metin))
```

`calistir` başında:

```python
    temiz_gecmis = [{**m, "content": sifresiz(m["content"])} for m in gecmis]
    temiz_soru = sifresiz(soru)
```

ve `yon_belirle(model, temiz_soru, temiz_gecmis)`, `sohbet(temiz_soru, temiz_gecmis, ...)`, `hizli(temiz_soru, temiz_gecmis, ...)`, `derin/hizli` (görev dışı modlar) için de `temiz_soru, temiz_gecmis`; `oneriler(model, temiz_soru, cevap)`. `gorev.calistir(soru, model, gecmis)` gerçek metinleri alır (yer tutucu ve gizleme orada yapılır).

`sunucu.py` `baslik()`:

```python
        return {"baslik": baslik_uret(istek.model, sifresiz(istek.soru))}
```

(`from .asistan import baslik_uret, calistir, sifresiz`; test `sunucu.baslik_uret`'i yamaladığı için çağrı modül özniteliği üzerinden yapılır — mevcut `from .asistan import baslik_uret` zaten bunu sağlar.)

- [ ] **Step 9: Testleri çalıştır**

Run: `.venv/Scripts/python -m pytest tests/test_gorev.py tests/test_sunucu.py tests/test_koruma.py -q`
Expected: hepsi geçer. `test_sayfa_sifreyi_adrese_koydurtamaz` ve `test_onceki_mesajdaki_sifre_kayitta_ve_istemde_gizlenir` değişmeden geçmeli (model gerçek şifreyi yazmaya çalışırsa eski kurallar yine engeller).

- [ ] **Step 10: Tüm paket ve commit**

Run: `.venv/Scripts/python -m pytest -q` → hepsi geçer.

```bash
git add sonda/koruma.py sonda/gorev/dongu.py sonda/gorev/promptlar.py sonda/asistan.py sonda/sunucu.py tests/test_koruma.py tests/test_gorev.py tests/test_sunucu.py
git commit -m "Şifre yer tutucu: görevde verilen şifre hiçbir modele gitmez, gerçek değeri kod yazar"
```

---

### Task 5: Arayüz — Ayarlar çekmecesi ve bulut hata ipucu

**Files:**
- Modify: `static/index.html`, `tests/test_arayuz.py`

**Interfaces:**
- Consumes: `GET /api/ayarlar`, `POST/DELETE /api/ayarlar/gemini`, `GET /api/modeller`, `hata` olayındaki `bulut` alanı (Task 3)
- Produces: `#ayarlar-ac` butonu; çekmecede `#gemini-anahtar` (password), `[data-gemini-kaydet]`, `[data-gemini-sil]`, `.ayar-durum`

- [ ] **Step 1: Arayüz testini yaz**

`tests/test_arayuz.py` — `arayuz` fikstürüne ayar yamaları ekle (`mp.setattr` satırlarının yanına):

```python
    from sonda import ayarlar
    from sonda.model import ModelHatasi, gemini_saglayici
    mp.setattr(ayarlar, "DOSYA", Path(tempfile.mkdtemp()) / "ayarlar.json")
    mp.delenv("GEMINI_API_KEY", raising=False)

    def dogrula(a):
        if a == "YANLIS":
            raise ModelHatasi("Gemini anahtarı geçersiz ya da yetkisiz. Ayarlar'dan kontrol et.")
    mp.setattr(gemini_saglayici, "anahtar_dogrula", dogrula)
    mp.setattr(gemini_saglayici, "modeller",
               lambda: [{"ad": "gemini:gemini-flash-latest", "etiket": "Gemini Flash (bulut, hızlı)"}]
               if ayarlar.gemini_anahtari() else [])
```

(`import tempfile` ve `from pathlib import Path` dosya başına.)

Test:

```python
def test_ayarlar_gemini_anahtari(arayuz):
    s = _sayfa(arayuz)
    s.click("#ayarlar-ac")
    s.fill("#gemini-anahtar", "YANLIS")
    s.click("[data-gemini-kaydet]")
    s.wait_for_selector(".ayar-durum.hata")
    assert "geçersiz" in s.inner_text(".ayar-durum")
    s.fill("#gemini-anahtar", "AIzaDOGRUabcd")
    s.click("[data-gemini-kaydet]")
    s.wait_for_selector(".ayar-durum.tamam")
    assert "…abcd" in s.inner_text("#cekmece-govde") and "DOGRU" not in s.inner_text("#cekmece-govde")
    s.wait_for_selector("#model option[value='gemini:gemini-flash-latest']", state="attached")
    assert "(bulut" in s.inner_text("#model")
    assert "Google" in s.inner_text("#cekmece-govde")  # gizlilik notu
    s.click("[data-gemini-sil]")
    s.wait_for_function("!document.querySelector(\"#model option[value='gemini:gemini-flash-latest']\")")
    s.close()
```

- [ ] **Step 2: Başarısız olduğunu gör**

Run: `.venv/Scripts/python -m pytest tests/test_arayuz.py -q -k ayarlar`
Expected: FAIL — `#ayarlar-ac` bulunamadı (zaman aşımı).

- [ ] **Step 3: `static/index.html`**

SVG sembollerine (`i-hafiza`'nın altına) bir anahtar simgesi:

```html
  <symbol id="i-ayar" viewBox="0 0 24 24"><circle cx="8" cy="15" r="4"/><path d="m10.8 12.2 8.2-8.2M16 7l2.5 2.5M14 9l2 2"/></symbol>
```

Hafıza butonunun hemen altına:

```html
    <button class="yeni-btn hafiza-btn" id="ayarlar-ac"><svg class="ik"><use href="#i-ayar"/></svg>Ayarlar</button>
```

CSS (hafıza stillerinin altına):

```css
.ayar-alan { display: flex; flex-direction: column; gap: 8px; margin: 0 6px 12px; }
.ayar-alan input { border: 1px solid var(--cizgi); border-radius: 9px; padding: 8px 10px; background: var(--yuzey); color: inherit; font: inherit; }
.ayar-butonlar { display: flex; gap: 8px; }
.ayar-butonlar button { border: 1px solid var(--cizgi); background: none; border-radius: 9px; padding: 7px 12px; font-size: 13.5px; color: inherit; }
.ayar-butonlar [data-gemini-sil] { color: var(--hata); }
.ayar-durum { font-size: 13.5px; margin: 0 6px 12px; }
.ayar-durum.hata { color: var(--hata); }
```

Model listesini yeniden yüklenebilir yap — mevcut `fetch("/api/modeller")...` bloğunu fonksiyona çevir:

```js
function modelleriYukle() {
  return fetch("/api/modeller").then(r => r.json()).then(liste => {
    const sec = $("#model");
    const onceki = sec.value;
    sec.innerHTML = liste.length ? liste.map(m => `<option value="${m.ad}">${kacis(m.etiket)}</option>`).join("")
                                 : "<option value=''>Model bulunamadı</option>";
    const k = onceki || depo.oku("sonda-model", null);
    if (k && liste.some(m => m.ad === k)) sec.value = k;
  }).catch(() => { $("#model").innerHTML = "<option value=''>Sunucuya ulaşılamadı</option>"; });
}
modelleriYukle();
```

Ayarlar paneli (hafıza panelinin altına; aynı çekmeceyi `hafiza-modu` sınıfıyla paylaşır, böylece kapatma/Escape davranışı aynen çalışır):

```js
// ---------- ayarlar paneli (sağ çekmecede)
async function ayarlarCiz(durum = "") {
  let a = { gemini: { var: false, son4: "" } };
  try { a = await (await fetch("/api/ayarlar")).json(); } catch {}
  U.classList.add("hafiza-modu");
  $("#cekmece-baslik").textContent = "Ayarlar";
  $("#cekmece-govde").innerHTML = `
    <p class="hafiza-aciklama"><b>Gemini (bulut model)</b><br>Anahtar eklersen model seçicide Gemini Flash ve Pro çıkar. Anahtar yalnızca bu bilgisayarda saklanır. Bulut model seçtiğinde soruların ve ziyaret edilen sayfaların içeriği Google'a gider; hesaplarınla çalışırken ücretli katman önerilir. Görevde verdiğin şifre hiçbir modele gönderilmez.</p>
    <div class="ayar-alan">
      <input id="gemini-anahtar" type="password" autocomplete="off" placeholder="${a.gemini.var ? `Kayıtlı anahtar ${kacis(a.gemini.son4)}` : "Gemini API anahtarı"}">
      <div class="ayar-butonlar"><button data-gemini-kaydet>Kaydet ve test et</button>${a.gemini.var ? "<button data-gemini-sil>Sil</button>" : ""}</div>
    </div>
    ${durum}`;
  U.classList.add("cekmece-acik");
}
$("#ayarlar-ac").onclick = () => { ayarlarCiz(); U.classList.remove("mobil-menu"); };
```

Çekmece gövdesi tıklama dinleyicisine (mevcut `$("#cekmece-govde").addEventListener("click", ...)` içinde, başa) ekle:

```js
  if (e.target.closest("[data-gemini-kaydet]")) {
    const btn = e.target.closest("[data-gemini-kaydet]");
    btn.disabled = true; btn.textContent = "Test ediliyor…";
    const r = await fetch("/api/ayarlar/gemini", { method: "POST", headers: { "Content-Type": "application/json" },
                                                  body: JSON.stringify({ anahtar: $("#gemini-anahtar").value }) });
    const j = await r.json().catch(() => ({}));
    await modelleriYukle();
    return ayarlarCiz(r.ok ? `<p class="ayar-durum tamam">Anahtar kaydedildi (${kacis(j.son4)}).</p>`
                           : `<p class="ayar-durum hata">${kacis(j.detail || "Kaydedilemedi.")}</p>`);
  }
  if (e.target.closest("[data-gemini-sil]")) {
    await fetch("/api/ayarlar/gemini", { method: "DELETE" });
    await modelleriYukle();
    bildir("Gemini anahtarı silindi");
    return ayarlarCiz();
  }
```

`hafizaCiz`'in başındaki `if (!ac && !U.classList.contains("hafiza-modu")) return;` satırı, ayarlar paneli açıkken 8 sn sonraki `hafizaCiz()` çağrısının paneli ezmesine yol açar. Bunu önlemek için `ayarlarCiz` `U.dataset.panel = "ayarlar"`, `hafizaCiz(true)` `U.dataset.panel = "hafiza"` atasın ve koşul `if (!ac && U.dataset.panel !== "hafiza") return;` olsun (`cekmeceAc` içinde `U.dataset.panel = ""`).

Hata ipucu satırını değiştir:

```js
        else if (o.tur === "hata") m.hata = o.bulut ? o.metin : `Bir hata oluştu: ${o.metin}.` + (/ollama|connect|model/i.test(o.metin) ? " Ollama'nın açık olduğunu ve seçili modelin indirildiğini kontrol et." : "");
```

- [ ] **Step 4: Testleri çalıştır**

Run: `.venv/Scripts/python -m pytest tests/test_arayuz.py -q`
Expected: hepsi geçer.

- [ ] **Step 5: Elle görsel kontrol**

`run` becerisiyle sunucuyu aç (`.venv/Scripts/python server.py`), Ayarlar panelinin açık ve koyu temada okunduğunu, mobil genişlikte (≤ 700px) çekmecenin tam ekran açıldığını gör.

- [ ] **Step 6: Tüm paket ve commit**

Run: `.venv/Scripts/python -m pytest -q` → hepsi geçer.

```bash
git add static/index.html tests/test_arayuz.py
git commit -m "Arayüz: Ayarlar çekmecesi (Gemini anahtarı), bulut modeller ve Türkçe bulut hataları"
```

---

### Task 6: Gerçek Gemini testleri ve belgeler

**Files:**
- Create: `tests/test_gemini_gercek.py`
- Modify: `pytest.ini`, `README.md`, `docs/yol-haritasi.md`, `docs/superpowers/specs/2026-09-25-gemini-saglayici-design.md` (Durum satırı)

**Interfaces:**
- Consumes: her şey (Task 1-5)
- Produces: `-m gemini` işaretli testler

- [ ] **Step 1: `pytest.ini`**

```ini
[pytest]
testpaths = tests
markers =
    model: gerçek Ollama modeli gerektirir (yavaş); -m model ile çalıştır
    gemini: gerçek Gemini API gerektirir (anahtar yoksa atlanır); -m gemini ile çalıştır
addopts = -m "not model and not gemini"
```

- [ ] **Step 2: `tests/test_gemini_gercek.py`**

```python
"""Gerçek Gemini API ile uçtan uca denemeler. Çalıştır: .venv/Scripts/python -m pytest -m gemini -v -s"""
import json

import pytest

from sonda import ayarlar, gorev
from sonda.arastirma.araclar import ARACLAR
from sonda.model import gemini_saglayici, sohbet

pytestmark = [pytest.mark.gemini,
              pytest.mark.skipif(not ayarlar.gemini_anahtari(), reason="Gemini anahtarı yok")]


@pytest.fixture(scope="module")
def flash():
    return next(m["ad"] for m in gemini_saglayici.modeller() if "Flash" in m["etiket"])


def test_json(flash):
    y = sohbet(flash, [{"role": "user", "content": 'Türkiye\'nin başkenti? Sadece JSON: {"sehir": "..."}'}], json=True)
    assert json.loads(y.metin)["sehir"].lower().startswith("ankara")


def test_akis(flash):
    metin = "".join(p.metin for p in sohbet(flash, [{"role": "user", "content": "1'den 5'e kadar say."}], akis=True))
    assert "5" in metin


def test_arac_gidis_donus(flash):
    mesajlar = [{"role": "user", "content": "1234*5678 kaç? hesapla aracını kullan."}]
    y = sohbet(flash, mesajlar, araclar=ARACLAR)
    assert y.arac_cagrilari and y.arac_cagrilari[0].ad == "hesapla"
    c = y.arac_cagrilari[0]
    mesajlar += [{"role": "assistant", "content": "", "tool_calls": [{"function": {"name": c.ad, "arguments": c.argumanlar}, "imza": c.imza}]},
                 {"role": "tool", "content": "7006652", "tool_name": "hesapla"}]
    assert "7006652" in sohbet(flash, mesajlar, araclar=ARACLAR).metin.replace(".", "").replace(",", "")


def test_gorsel(flash, tarayici, site):
    tarayici.git(f"{site}/giris.html")
    y = sohbet(flash, [{"role": "user", "content": "Bu ekranda hangi form var? Tek cümle.",
                        "images": [tarayici.ekran_goruntusu()]}])
    assert y.metin.strip()


def test_yerel_sitede_gorev(flash, yerel_tarayici_ac, site):
    olaylar = list(gorev.calistir(f"{site}/magaza/index.html adresindeki mağazada en ucuz 1 TB NVMe SSD'yi ve fiyatını bul.",
                                  flash, tarayici_ac=yerel_tarayici_ac))
    cevap = "".join(o["metin"] for o in olaylar if o["tur"] == "token")
    print(cevap)
    assert "Kioxia" in cevap and ("2.649" in cevap or "2649" in cevap)
```

- [ ] **Step 3: Anahtarsız çalıştır: atlanmalı**

Run: `.venv/Scripts/python -m pytest -m gemini -q`
Expected: anahtar yoksa `5 skipped`. Anahtar varsa `5 passed` (başarısız olursa sistematik hata ayıklama ile düzelt; özellikle düşünme ayarı ve düşünce imzası).

- [ ] **Step 4: Belgeler**

- `README.md`: "Models" bölümüne Gemini paragrafı: Ayarlar'dan anahtar ekleme, `GEMINI_API_KEY` yedeği, "(cloud)" etiketinin anlamı, görev şifresinin modele gitmediği.
- Spec'te `*Durum: onay bekliyor*` → `*Durum: uygulandı*`.
- `docs/yol-haritasi.md`: Gemini sağlayıcı tamamlandı satırı; açık iş: gerçek dünya karşılaştırması.

- [ ] **Step 5: Tüm paket ve commit**

Run: `.venv/Scripts/python -m pytest -q` → hepsi geçer.

```bash
git add pytest.ini tests/test_gemini_gercek.py README.md docs
git commit -m "Gemini: gerçek API testleri (-m gemini) ve belgeler"
```

- [ ] **Step 6: Gerçek dünya karşılaştırması (kullanıcıyla)**

Kullanıcı Ayarlar'dan anahtarını ekledikten sonra Upwork profil inceleme görevini Gemini Flash ile çalıştır; süreyi ve cevabın kalitesini yerel modeldeki 22 dakikalık çalışmayla karşılaştır ve `docs/yol-haritasi.md`'ye yaz. Bu adım kullanıcının Chrome'unu ve hesabını kullandığı için kullanıcı hazır olduğunda yapılır.
