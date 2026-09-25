import pytest

from conftest import ihlaller


def bul(sayfa, metin):
    return next(o for o in sayfa["ogeler"] if metin in (o["metin"] + o["yer"] + o["aria"]))


def test_bak_numarali_ogeleri_listeler(tarayici, site):
    tarayici.git(f"{site}/magaza/index.html")
    s = tarayici.bak()
    assert s["baslik"] == "TeknoPazar" and s["url"].endswith("/magaza/index.html")
    kutu = bul(s, "Ürün, kategori")
    assert kutu["etiket"] == "input" and kutu["ad"] == "q" and kutu["form"] == 0
    assert [o["no"] for o in s["ogeler"]] == list(range(1, len(s["ogeler"]) + 1))
    assert "TeknoPazar" in s["metin"]


def test_yaz_ve_enter_ile_arama(tarayici, site):
    tarayici.git(f"{site}/magaza/index.html")
    kutu = bul(tarayici.bak(), "Ürün, kategori")
    tarayici.yaz(kutu["no"], "nvme", enter=True)
    assert "ara.html?q=nvme" in tarayici.url
    assert "Kioxia" in tarayici.bak()["metin"]


def test_yaz_enter_basmaz(tarayici, site):
    tarayici.git(f"{site}/magaza/index.html")
    kutu = bul(tarayici.bak(), "Ürün, kategori")
    tarayici.yaz(kutu["no"], "nvme")
    assert tarayici.url.endswith("/magaza/index.html")


def test_tikla_baglantiyi_acar(tarayici, site):
    tarayici.git(f"{site}/magaza/ara.html?q=kioxia")
    tarayici.tikla(bul(tarayici.bak(), "Kioxia")["no"])
    assert "urun.html?id=2" in tarayici.url and tarayici.baslik.startswith("Kioxia")


def test_sec_ve_siralama(tarayici, site):
    tarayici.git(f"{site}/magaza/ara.html?q=ssd")
    secim = next(o for o in tarayici.bak()["ogeler"] if o["etiket"] == "select")
    assert "Fiyat artan" in secim["secenekler"]
    tarayici.sec(secim["no"], "Fiyat artan")
    ilk = next(o for o in tarayici.bak()["ogeler"] if o["etiket"] == "a")
    assert "Kingston" in ilk["metin"]


def test_yeni_sekme_baglantisi_ayni_sekmede_acilir(tarayici, site):
    tarayici.git(f"{site}/magaza/urun.html?id=1")
    tarayici.tikla(bul(tarayici.bak(), "yeni sekme")["no"])
    assert tarayici.url.endswith("/magaza/index.html")
    assert len(tarayici.sayfa.context.pages) == 1


def test_oge_bilgisi_form_kardeslerini_verir(tarayici, site):
    tarayici.git(f"{site}/giris.html")
    s = tarayici.bak()
    bilgi = tarayici.oge_bilgisi(bul(s, "Giriş Yap")["no"])
    assert bilgi["oge"]["metin"] == "Giriş Yap"
    assert any(f["tip"] == "password" for f in bilgi["form_ogeleri"])


def test_oge_bilgisi_olmayan_numara(tarayici, site):
    tarayici.git(f"{site}/giris.html")
    tarayici.bak()
    assert tarayici.oge_bilgisi(999) is None


def test_etiket_metni_label_icinden_gelir(tarayici, site):
    tarayici.git(f"{site}/magaza/odeme.html")
    kart = next(o for o in tarayici.bak()["ogeler"] if o["ad"] == "cardnumber")
    assert "Kart Numarası" in kart["metin"] and kart["otomatik"] == "cc-number"


def test_kaydir_geri_ekran_vurgula_tam_metin(tarayici, site):
    tarayici.git(f"{site}/magaza/index.html")
    tarayici.git(f"{site}/magaza/ara.html?q=ssd")
    tarayici.bak()
    tarayici.kaydir("asagi")
    tarayici.vurgula(1)
    assert tarayici.ekran_goruntusu()[:2] == b"\xff\xd8"  # JPEG
    assert "Samsung" in tarayici.tam_metin()
    tarayici.geri()
    assert tarayici.url.endswith("/magaza/index.html")


def test_kapali_adres_hata_firlatir(tarayici):
    with pytest.raises(Exception):
        tarayici.git("http://127.0.0.1:9/")  # kapalı port: hata beklenir, gorev.py yakalar


def test_bu_testler_ihlal_uretmez(tarayici, site):
    tarayici.git(f"{site}/magaza/odeme.html")
    assert ihlaller(tarayici) == []
