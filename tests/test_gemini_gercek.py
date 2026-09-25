"""Gerçek Gemini API ile uçtan uca denemeler. Çalıştır: .venv/Scripts/python -m pytest -m gemini -v -s"""
import json
import time

import pytest

from sonda import ayarlar, gorev
from sonda.arastirma.araclar import ARACLAR
from sonda.model import gemini_saglayici, sohbet

pytestmark = [pytest.mark.gemini,
              pytest.mark.skipif(not ayarlar.gemini_anahtari(), reason="Gemini anahtarı yok")]


@pytest.fixture(scope="module", params=["flash-lite", "flash"])
def model(request):
    """Listelenen iki ucuz model de sınanır."""
    modeller = gemini_saglayici.modeller()
    return next(m["ad"] for m in modeller if m["ad"].endswith(f"-{request.param}-latest")) \
        if any(m["ad"].endswith(f"-{request.param}-latest") for m in modeller) else modeller[0 if request.param == "flash-lite" else 1]["ad"]


def test_json(model):
    y = sohbet(model, [{"role": "user", "content": 'Türkiye\'nin başkenti? Sadece JSON: {"sehir": "..."}'}], json=True)
    assert json.loads(y.metin)["sehir"].lower().startswith("ankara")


def test_akis(model):
    metin = "".join(p.metin for p in sohbet(model, [{"role": "user", "content": "1'den 5'e kadar say."}], akis=True))
    assert "5" in metin


def test_arac_gidis_donus(model):
    mesajlar = [{"role": "user", "content": "1234*5678 kaç? hesapla aracını kullan."}]
    y = sohbet(model, mesajlar, araclar=ARACLAR)
    assert y.arac_cagrilari and y.arac_cagrilari[0].ad == "hesapla"
    c = y.arac_cagrilari[0]
    mesajlar += [{"role": "assistant", "content": "", "tool_calls": [
                     {"function": {"name": c.ad, "arguments": c.argumanlar}, "imza": c.imza}]},
                 {"role": "tool", "content": "7006652", "tool_name": "hesapla"}]
    cevap = sohbet(model, mesajlar, araclar=ARACLAR).metin
    assert "7006652" in cevap.replace(".", "").replace(",", "")


def test_imzasiz_arac_cagrisi_kabul_edilir(model):
    """Hızlı mod ilk aramayı modelsiz ekler: imzasız çağrı Gemini'de hata vermemeli."""
    y = sohbet(model, [{"role": "user", "content": "İstanbul'da bugün hava kaç derece?"},
                       {"role": "assistant", "content": "", "tool_calls": [
                           {"function": {"name": "web_ara", "arguments": {"sorgular": ["hava"]}}}]},
                       {"role": "tool", "content": "İstanbul 21°C güneşli", "tool_name": "web_ara"}],
               araclar=ARACLAR)
    assert y.metin.strip() or y.arac_cagrilari  # 400 yok: istek kabul edildi (cevap ya da yeni arama)


def test_gorsel(model, tarayici, site):
    tarayici.git(f"{site}/giris.html")
    y = sohbet(model, [{"role": "user", "content": "Bu ekranda hangi form var? Tek cümle.",
                        "images": [tarayici.ekran_goruntusu()]}])
    assert y.metin.strip()


def test_yerel_sitede_gorev(model, yerel_tarayici_ac, site):
    basla = time.time()
    olaylar = list(gorev.calistir(f"{site}/magaza/index.html adresindeki mağazada en ucuz 1 TB NVMe SSD'yi ve fiyatını bul.",
                                  model, tarayici_ac=yerel_tarayici_ac))
    cevap = "".join(o["metin"] for o in olaylar if o["tur"] == "token")
    print(f"\n{model}: {time.time() - basla:.0f} sn\n{cevap[:400]}")
    assert "Kioxia" in cevap and ("2.649" in cevap or "2649" in cevap)


def test_derin_arastirma(model, monkeypatch):
    """Gerçek hata: derin moddaki sistem-yalnız çağrılar Gemini'de 'contents are required' veriyordu."""
    from sonda import asistan
    monkeypatch.setattr(asistan, "hafizayi_guncelle", lambda *a: None)
    olaylar = list(asistan.calistir("Türkiye'de 2026'da elektrikli araç satışları", [], model, "derin", oneri=False))
    assert not [o for o in olaylar if o["tur"] == "hata"]
    assert len("".join(o["metin"] for o in olaylar if o["tur"] == "token")) > 200
