from fastapi.testclient import TestClient

from sonda import asistan, gorev, sunucu

istemci = TestClient(sunucu.app, base_url="http://127.0.0.1")


def test_bilinmeyen_gorev_komutu():
    assert istemci.post("/api/gorev/yok/devam").json() == {"tamam": False}


def test_gecersiz_komut_400():
    assert istemci.post("/api/gorev/yok/sil").status_code == 400


def test_calistir_gorev_moduna_yonlendirir(monkeypatch):
    cagri = {}

    def sahte(soru, model, gecmis=(), serbest=False):
        cagri.update(soru=soru, model=model, gecmis=list(gecmis), serbest=serbest)
        yield {"tur": "gorev_basladi", "id": "x"}
        yield {"tur": "token", "metin": "tamam"}
        yield {"tur": "cevap_bitti", "metin": "tamam"}
    monkeypatch.setattr(gorev, "calistir", sahte)
    monkeypatch.setattr(asistan, "hafizayi_guncelle", lambda *a: None)
    monkeypatch.setattr(asistan, "yon_belirle", lambda *a: "gorev")
    olaylar = list(asistan.calistir("ssd bul", [{"role": "user", "content": "a"}], "m", "gorev"))
    assert cagri["soru"] == "ssd bul" and cagri["gecmis"] and cagri["serbest"] is False
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



def test_yabanci_host_basligi_reddedilir():
    """Final inceleme I8: DNS rebinding ile kötü niyetli bir sayfa yerel sunucuya görev yaptıramasın."""
    assert istemci.get("/api/durum", headers={"host": "kotu-site.com"}).status_code == 400
    assert istemci.post("/api/sor", json={"soru": "x", "model": "m", "mod": "gorev"},
                        headers={"host": "kotu-site.com"}).status_code == 400
    assert istemci.get("/api/durum", headers={"host": "localhost:8765"}).status_code == 200


# ---- Gemini: ayarlar ve model listesi
import pytest

from sonda import ayarlar, yonlendirme
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
    govde = istemci.get("/api/ayarlar").json()
    assert govde == {"gemini": {"var": True, "son4": "…abcd"}}
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
    monkeypatch.setattr(gemini_saglayici, "modeller", lambda: [{"ad": "gemini:gemini-flash-latest", "etiket": "E"}])
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


def test_yonlendirme_ve_gecmis_sifreyi_gormez(monkeypatch):
    gorulen = []
    monkeypatch.setattr(asistan, "hafizayi_guncelle", lambda *a: None)
    monkeypatch.setattr(asistan, "yon_belirle", lambda model, soru, gecmis: gorulen.append((soru, gecmis)) or "sohbet")
    monkeypatch.setattr(asistan, "sohbet", lambda soru, gecmis, *a: gorulen.append((soru, gecmis)) or iter([]))
    list(asistan.calistir("upwork şifrem Parola-7788 ile gir", [{"role": "user", "content": "şifrem Gizli-4455"}],
                          "gemini:x", "gorev"))
    assert gorulen and "Parola-7788" not in repr(gorulen) and "Gizli-4455" not in repr(gorulen)


def test_baslik_sifreyi_gormez(monkeypatch):
    gorulen = []
    monkeypatch.setattr(sunucu, "baslik_uret", lambda model, soru: gorulen.append(soru) or "Başlık")
    istemci.post("/api/baslik", json={"soru": "upwork şifrem Parola-7788 ile gir", "model": "gemini:x"})
    assert gorulen and "Parola-7788" not in gorulen[0]


# ---- Final inceleme: şifre başka yollardan modele gitmesin
def _yakala(monkeypatch, hedef="hizli"):
    gorulen = []
    monkeypatch.setattr(asistan, "hafizayi_guncelle", lambda model, mesaj: gorulen.append(("hafiza", mesaj)))
    monkeypatch.setattr(asistan, hedef, lambda *a, **k: gorulen.append(a) or iter([]))
    monkeypatch.setattr(asistan, "yon_belirle", lambda model, soru, gecmis: gorulen.append((soru, gecmis)) or "sohbet")
    return gorulen


def test_diger_sohbet_basliklari_sifresiz(monkeypatch):
    gorulen = _yakala(monkeypatch)
    list(asistan.calistir("dolar kaç", [], "gemini:x", "hizli", (), ["instagram şifre Kedi-1234 ile gir"]))
    assert gorulen and "Kedi-1234" not in repr(gorulen)


def test_baslik_yedegi_sifresiz(monkeypatch):
    monkeypatch.setattr(sunucu, "baslik_uret", lambda *a: (_ for _ in ()).throw(RuntimeError("kota")))
    r = istemci.post("/api/baslik", json={"soru": "instagram şifre Kedi-1234 ile gir", "model": "gemini:x"})
    assert "Kedi-1234" not in r.json()["baslik"]


def test_hafiza_cikarimi_sifreyi_gormez(monkeypatch):
    import time
    gorulen = _yakala(monkeypatch)
    list(asistan.calistir("benim instagram şifrem Kedi-1234, güçlü mü?", [], "gemini:x", "hizli"))
    time.sleep(0.2)  # hafıza güncellemesi arka planda
    assert any(g[0] == "hafiza" for g in gorulen) and "Kedi-1234" not in repr(gorulen)


def test_onceki_mesajdaki_sifre_tekrarlaninca_gizlenir(monkeypatch):
    gorulen = _yakala(monkeypatch, "sohbet")
    list(asistan.calistir("Aynı hesapla Kedi-1234 kullanarak twitter.com'a da gir",
                          [{"role": "user", "content": "instagram şifrem Kedi-1234"}], "gemini:x", "gorev"))
    assert gorulen and "Kedi-1234" not in repr(gorulen)


def test_serbest_izni_istekten_goreve_gecer(monkeypatch):
    cagri = {}

    def sahte(soru, model, gecmis=(), serbest=False):
        cagri["serbest"] = serbest
        yield {"tur": "cevap_bitti", "metin": ""}
    monkeypatch.setattr(gorev, "calistir", sahte)
    monkeypatch.setattr(asistan, "yon_belirle", lambda *a: "gorev")
    istemci.post("/api/sor", json={"soru": "başvur", "model": "m", "mod": "gorev", "serbest": True}).read()
    assert cagri["serbest"] is True
