import threading

import pytest

import gorev
from conftest import ihlaller

isinde = gorev.tarayici_isinde  # Playwright nesneleri tarayıcı iş parçacığına bağlıdır


class SahteModel:
    """Sırayla verilen eylemleri döndürür; her çağrıda aldığı istemi kaydeder."""

    def __init__(self, eylemler):
        self.eylemler, self.istemler, self.ekranlar = list(eylemler), [], []

    def __call__(self, model, istem, ekran=None):
        self.istemler.append(istem)
        self.ekranlar.append(ekran)
        return self.eylemler.pop(0) if self.eylemler else {"eylem": "bitir", "sonuc": "bitti"}


@pytest.fixture
def sahte(monkeypatch):
    def kur(eylemler):
        m = SahteModel(eylemler)
        monkeypatch.setattr(gorev, "_karar_al", m)
        monkeypatch.setattr(gorev, "_sonuc_yaz", lambda *a, **k: iter([{"tur": "token", "metin": "ÖZET"},
                                                                          {"tur": "cevap_bitti", "metin": "ÖZET"}]))
        return m
    return kur


def calistir(yerel_tarayici_ac, metin="görev", komutlar=None, kayit=None):
    """Görevi çalıştırır; 'kullaniciya' olayı gelince sıradaki komutu verir. Olay listesini döner.
    kayit verilirse Tarayici nesnesi kayit["t"]'ye konur (ihlal kontrolü için)."""
    komutlar = list(komutlar or [])

    def ac():
        t = yerel_tarayici_ac()
        if kayit is not None:
            kayit["t"] = t
            t._kapat_asil, t._kapat = t._kapat, None  # testte ihlalleri okuyabilmek için açık bırak
        return t
    olaylar = []
    for o in gorev.calistir(metin, "sahte", tarayici_ac=ac):
        olaylar.append(o)
        if o["tur"] == "kullaniciya":
            gorev.komut_ver(o["id"], komutlar.pop(0) if komutlar else "durdur")
    return olaylar


def turler(olaylar):
    return [o["tur"] for o in olaylar]


def test_basit_gezinme_ve_not(sahte, yerel_tarayici_ac, site):
    m = sahte([{"eylem": "git", "url": f"{site}/magaza/ara.html?q=nvme"},
               {"eylem": "not_al", "metin": "Kioxia 1TB 2.649 TL"},
               {"eylem": "bitir", "sonuc": "En ucuz Kioxia"}])
    o = calistir(yerel_tarayici_ac)
    assert o[0]["tur"] == "gorev_basladi"
    assert any(x["tur"] == "adim" and x["tip"] == "gezin" for x in o)
    assert any(x["tur"] == "adim" and x["tip"] == "not" for x in o)
    assert turler(o)[-1] == "cevap_bitti"
    assert "Kioxia 1TB 2.649 TL" in m.istemler[2]          # not sonraki istemde görünür
    assert "[1] kutu" in m.istemler[1] or "[1]" in m.istemler[1]  # sayfa öğeleri istemde


def test_yasak_buton_engellenir_ve_kullaniciya_birakilir(sahte, yerel_tarayici_ac, site):
    kayit = {}
    def adimlar():
        return [{"eylem": "git", "url": f"{site}/giris.html"}, {"eylem": "tikla", "no": None}]
    m = sahte(adimlar())
    # tıklanacak numarayı bilmediğimizden ikinci eylemi istem geldiğinde belirle
    asil = m.__call__
    def akilli(model, istem, ekran=None):
        karar = asil(model, istem, ekran)
        if karar.get("eylem") == "tikla":
            satir = next(s for s in istem.splitlines() if "Giriş Yap" in s and s.startswith("["))
            karar["no"] = int(satir[1:satir.index("]")])
        return karar
    gorev._karar_al = akilli
    o = calistir(yerel_tarayici_ac, komutlar=["durdur"], kayit=kayit)
    assert "kullaniciya" in turler(o)
    assert any(x["tur"] == "adim" and x["tip"] == "engel" for x in o)
    assert isinde(ihlaller, kayit["t"]) == []
    isinde(kayit["t"]._kapat_asil)


def test_hassas_alana_yazma_engellenir(sahte, yerel_tarayici_ac, site):
    kayit = {}
    m = sahte([{"eylem": "git", "url": f"{site}/magaza/odeme.html"}])
    asil = m.__call__
    def akilli(model, istem, ekran=None):
        if len(m.istemler) == 1:
            satir = next(s for s in istem.splitlines() if "Kart Numarası" in s and s.startswith("["))
            m.istemler.append(istem)
            return {"eylem": "yaz", "no": int(satir[1:satir.index("]")]), "metin": "4111111111111111"}
        return asil(model, istem, ekran)
    gorev._karar_al = akilli
    o = calistir(yerel_tarayici_ac, komutlar=["durdur"], kayit=kayit)
    assert "kullaniciya" in turler(o)
    assert isinde(ihlaller, kayit["t"]) == []
    assert isinde(lambda: kayit["t"].sayfa.input_value("[name=cardnumber]")) == ""
    isinde(kayit["t"]._kapat_asil)


def test_devam_komutu_gorevi_surdurur(sahte, yerel_tarayici_ac, site):
    m = sahte([{"eylem": "git", "url": f"{site}/giris.html"},
               {"eylem": "sana_birak", "sebep": "Giriş yapman gerekiyor"},
               {"eylem": "bitir", "sonuc": "tamam"}])
    o = calistir(yerel_tarayici_ac, komutlar=["devam"])
    assert turler(o).count("kullaniciya") == 1
    assert {"tur": "devam_edildi", "komut": "devam"} in o
    assert "devam" in m.istemler[2].lower() and "kullanıcı" in m.istemler[2].lower()
    assert turler(o)[-1] == "cevap_bitti"


def test_durdur_komutu_bekleyen_gorevi_bitirir(sahte, yerel_tarayici_ac, site):
    sahte([{"eylem": "git", "url": f"{site}/giris.html"}, {"eylem": "sana_birak", "sebep": "?"},
           {"eylem": "git", "url": f"{site}/magaza/index.html"}])
    o = calistir(yerel_tarayici_ac, komutlar=["durdur"])
    assert not any(x["tur"] == "adim" and "magaza" in x.get("metin", "") for x in o)
    assert turler(o)[-1] == "cevap_bitti"


def test_bekleme_zaman_asimi(sahte, yerel_tarayici_ac, site, monkeypatch):
    monkeypatch.setattr(gorev, "BEKLEME_SURESI", 0.5)
    sahte([{"eylem": "sana_birak", "sebep": "?"}])
    olaylar = []
    for x in gorev.calistir("g", "sahte", tarayici_ac=yerel_tarayici_ac):
        olaylar.append(x)  # komut verilmez
    assert {"tur": "devam_edildi", "komut": "zaman_asimi"} in olaylar


def test_adim_siniri(sahte, yerel_tarayici_ac, site, monkeypatch):
    monkeypatch.setattr(gorev, "MAKS_ADIM", 3)
    m = sahte([{"eylem": "kaydir", "yon": "asagi"}] * 10)
    o = calistir(yerel_tarayici_ac)
    assert len(m.istemler) == 3 and turler(o)[-1] == "cevap_bitti"


def test_takilma_once_ekran_sonra_devret(sahte, yerel_tarayici_ac, site):
    m = sahte([{"eylem": "git", "url": f"{site}/magaza/index.html"}] * 6)
    o = calistir(yerel_tarayici_ac, komutlar=["durdur"])
    assert m.ekranlar[3] is not None           # 3. tekrardan sonraki istemde ekran görüntüsü
    assert "kullaniciya" in turler(o)           # 4. tekrarda devredilir


def test_olmayan_oge_geri_bildirimi(sahte, yerel_tarayici_ac, site):
    m = sahte([{"eylem": "git", "url": f"{site}/giris.html"}, {"eylem": "tikla", "no": 999}])
    calistir(yerel_tarayici_ac)
    assert "999" in m.istemler[2] and "yok" in m.istemler[2]


def test_hatali_eylem_gorevi_cokertmez(sahte, yerel_tarayici_ac, site):
    m = sahte([{"eylem": "git", "url": "http://127.0.0.1:9/"}])
    o = calistir(yerel_tarayici_ac)
    assert any(x["tur"] == "adim" and x["tip"] == "hata" for x in o)
    assert "başarısız" in m.istemler[1]


def test_git_javascript_engellenir(sahte, yerel_tarayici_ac):
    m = sahte([{"eylem": "git", "url": "javascript:alert(1)"}])
    calistir(yerel_tarayici_ac)
    assert "http" in m.istemler[1]


def test_koruma_taze_oge_bilgisini_kullanir(sahte, yerel_tarayici_ac, site):
    """Model 'Sepete Ekle'yi gördü; tıklama anına kadar buton metni 'Hemen Al' oldu -> engellenmeli."""
    kayit = {}
    m = sahte([{"eylem": "git", "url": f"{site}/magaza/urun.html?id=2"}])
    asil = m.__call__
    def akilli(model, istem, ekran=None):
        if len(m.istemler) == 1:
            m.istemler.append(istem)
            satir = next(s for s in istem.splitlines() if "Sepete Ekle" in s and s.startswith("["))
            kayit["t"].sayfa.evaluate("document.getElementById('ekle').textContent = 'Hemen Al'")
            return {"eylem": "tikla", "no": int(satir[1:satir.index("]")])}
        return asil(model, istem, ekran)
    gorev._karar_al = akilli
    o = calistir(yerel_tarayici_ac, komutlar=["durdur"], kayit=kayit)
    assert "kullaniciya" in turler(o)
    assert isinde(lambda: kayit["t"].sayfa.evaluate("localStorage.getItem('sepet')")) is None
    isinde(kayit["t"]._kapat_asil)


def test_kopan_baglanti_gorevi_durdurur(sahte, yerel_tarayici_ac, site):
    sahte([{"eylem": "sana_birak", "sebep": "?"}])
    akis = gorev.calistir("g", "sahte", tarayici_ac=yerel_tarayici_ac)
    for o in akis:
        if o["tur"] == "kullaniciya":
            gid = o["id"]
            break
    akis.close()  # arayüz bağlantıyı kopardı
    assert gid not in gorev.GOREVLER


def test_baglanti_hatasi_yardim_mesaji(monkeypatch):
    import tarayici

    def hata():
        raise tarayici.BaglantiHatasi(tarayici.BAGLANTI_YARDIMI)
    o = list(gorev.calistir("g", "sahte", tarayici_ac=hata))
    assert any(x["tur"] == "token" and "chrome://inspect" in x["metin"] for x in o)
    assert o[-1]["tur"] == "cevap_bitti"


def test_hassas_deger_istemde_gizlenir(sahte, yerel_tarayici_ac, site):
    m = sahte([{"eylem": "git", "url": f"{site}/giris.html"}])
    def ac():
        t = yerel_tarayici_ac()
        t.git(f"{site}/giris.html")
        t.sayfa.fill("[name=sifre]", "gizli123")  # kullanıcı yazmış gibi
        return t
    list(gorev.calistir("g", "sahte", tarayici_ac=ac))
    assert "gizli123" not in "\n".join(m.istemler)


def test_gorevler_ayni_kalici_is_parcaciginda_calisir(sahte, yerel_tarayici_ac):
    """Gerçek Chrome her yeni bağlantıda izin ister; bağlantının tekrar kullanılabilmesi için tüm görevler
    aynı iş parçacığında çalışmalı."""
    import threading
    kimlikler = []

    def ac():
        kimlikler.append(threading.get_ident())
        return yerel_tarayici_ac()
    for _ in range(2):
        sahte([{"eylem": "bitir", "sonuc": "x"}])
        list(gorev.calistir("g", "sahte", tarayici_ac=ac))
    assert len(kimlikler) == 2 and kimlikler[0] == kimlikler[1] != threading.get_ident()
