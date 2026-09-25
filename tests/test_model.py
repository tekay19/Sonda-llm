"""Model katmanı: sağlayıcı seçimi ve Ollama yanıtının ortak tiplere çevrilmesi."""
from types import SimpleNamespace as NS

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
