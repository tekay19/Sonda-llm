from fastapi.testclient import TestClient

import agent
import gorev
import server

istemci = TestClient(server.app)


def test_bilinmeyen_gorev_komutu():
    assert istemci.post("/api/gorev/yok/devam").json() == {"tamam": False}


def test_gecersiz_komut_400():
    assert istemci.post("/api/gorev/yok/sil").status_code == 400


def test_calistir_gorev_moduna_yonlendirir(monkeypatch):
    cagri = {}

    def sahte(soru, model, gecmis=()):
        cagri.update(soru=soru, model=model, gecmis=list(gecmis))
        yield {"tur": "gorev_basladi", "id": "x"}
        yield {"tur": "token", "metin": "tamam"}
        yield {"tur": "cevap_bitti", "metin": "tamam"}
    monkeypatch.setattr(gorev, "calistir", sahte)
    monkeypatch.setattr(agent, "_hafizayi_guncelle", lambda *a: None)
    olaylar = list(agent.calistir("ssd bul", [{"role": "user", "content": "a"}], "m", "gorev"))
    assert cagri["soru"] == "ssd bul" and cagri["gecmis"]
    assert [o["tur"] for o in olaylar] == ["gorev_basladi", "token", "bitti"]  # görevde öneri üretilmez


def test_gorev_modunda_hafiza_cikarimi_yapilmaz(monkeypatch):
    """Görev mesajında şifre olabilir: hafıza dosyasına yazılmamalı."""
    cagrilar = []
    monkeypatch.setattr(gorev, "calistir", lambda *a, **k: iter([{"tur": "cevap_bitti", "metin": ""}]))
    monkeypatch.setattr(agent, "_hafizayi_guncelle", lambda *a: cagrilar.append(a))
    list(agent.calistir("upwork şifrem abc123 ile gir", [], "m", "gorev"))
    import time
    time.sleep(0.2)
    assert cagrilar == []
