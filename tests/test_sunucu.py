from fastapi.testclient import TestClient

from sonda import asistan, gorev, sunucu

istemci = TestClient(sunucu.app)


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
    monkeypatch.setattr(asistan, "hafizayi_guncelle", lambda *a: None)
    monkeypatch.setattr(asistan, "yon_belirle", lambda *a: "gorev")
    olaylar = list(asistan.calistir("ssd bul", [{"role": "user", "content": "a"}], "m", "gorev"))
    assert cagri["soru"] == "ssd bul" and cagri["gecmis"]
    assert [o["tur"] for o in olaylar] == ["yon", "gorev_basladi", "token", "bitti"]  # görevde öneri üretilmez


def test_gorev_modunda_hafiza_cikarimi_yapilmaz(monkeypatch):
    """Görev mesajında şifre olabilir: hafıza dosyasına yazılmamalı."""
    cagrilar = []
    monkeypatch.setattr(gorev, "calistir", lambda *a, **k: iter([{"tur": "cevap_bitti", "metin": ""}]))
    monkeypatch.setattr(asistan, "hafizayi_guncelle", lambda *a: cagrilar.append(a))
    monkeypatch.setattr(asistan, "yon_belirle", lambda *a: "gorev")
    list(asistan.calistir("upwork şifrem abc123 ile gir", [], "m", "gorev"))
    import time
    time.sleep(0.2)
    assert cagrilar == []


# ---- Görev modunda yönlendirme: her mesaj tarayıcı görevi olmasın
def _yonlendir(monkeypatch, hedef):
    cagri = {}
    monkeypatch.setattr(asistan, "hafizayi_guncelle", lambda *a: None)
    monkeypatch.setattr(asistan, "yon_belirle", lambda *a: hedef)

    def sahte_gorev(*a, **k):
        cagri["gorev"] = True
        yield {"tur": "cevap_bitti", "metin": "g"}

    def sahte_sohbet(*a, **k):
        cagri["sohbet"] = True
        yield {"tur": "token", "metin": "rica ederim"}
        yield {"tur": "cevap_bitti", "metin": "rica ederim"}

    def sahte_hizli(*a, **k):
        cagri["hizli"] = True
        yield {"tur": "cevap_bitti", "metin": "h"}
    monkeypatch.setattr(gorev, "calistir", sahte_gorev)
    monkeypatch.setattr(asistan, "sohbet", sahte_sohbet)
    monkeypatch.setattr(asistan, "hizli", sahte_hizli)
    olaylar = list(asistan.calistir("teşekkürler", [{"role": "user", "content": "a"}], "m", "gorev"))
    return cagri, olaylar


def test_gorev_modunda_sohbet_mesaji_tarayici_acmaz(monkeypatch):
    cagri, olaylar = _yonlendir(monkeypatch, "sohbet")
    assert cagri == {"sohbet": True}
    assert olaylar[0] == {"tur": "yon", "hedef": "sohbet"}


def test_gorev_modunda_bilgi_sorusu_hizli_aramaya_gider(monkeypatch):
    cagri, olaylar = _yonlendir(monkeypatch, "bilgi")
    assert cagri == {"hizli": True} and olaylar[0] == {"tur": "yon", "hedef": "bilgi"}


def test_gorev_modunda_gorev_tarayiciya_gider(monkeypatch):
    cagri, olaylar = _yonlendir(monkeypatch, "gorev")
    assert cagri == {"gorev": True} and olaylar[0] == {"tur": "yon", "hedef": "gorev"}


def test_yon_belirle_cevabi_dogrular(monkeypatch):
    from sonda import yonlendirme
    monkeypatch.setattr(yonlendirme, "json_sor", lambda *a: {"hedef": "sohbet"})
    assert yonlendirme.yon_belirle("m", "sağ ol", []) == "sohbet"
    monkeypatch.setattr(yonlendirme, "json_sor", lambda *a: {"hedef": "saçma"})
    assert yonlendirme.yon_belirle("m", "x", []) == "gorev"
    monkeypatch.setattr(yonlendirme, "json_sor", lambda *a: (_ for _ in ()).throw(RuntimeError("ollama yok")))
    assert yonlendirme.yon_belirle("m", "x", []) == "gorev"


def test_diger_modlarda_yonlendirme_yok(monkeypatch):
    monkeypatch.setattr(asistan, "hafizayi_guncelle", lambda *a: None)
    monkeypatch.setattr(asistan, "yon_belirle", lambda *a: (_ for _ in ()).throw(AssertionError("çağrılmamalı")))
    monkeypatch.setattr(asistan, "hizli", lambda *a, **k: iter([{"tur": "cevap_bitti", "metin": ""}]))
    assert [o["tur"] for o in asistan.calistir("x", [], "m", "hizli", oneri=False)] == ["bitti"]
