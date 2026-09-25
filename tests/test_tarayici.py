import pytest

from sonda.tarayici import SekmeKapandi

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


def test_baglan_baglantiyi_yeniden_kullanir(monkeypatch):
    """Gerçek Chrome her CDP bağlantısında izin sorar: baglan() bağlantıyı önbelleğe almalı."""
    import threading

    from sonda.tarayici import baglanti as tr
    hazir, bitti = threading.Event(), threading.Event()

    def sunucu():  # uzaktan hata ayıklama portu açık bir Chromium (kullanıcının Chrome'u yerine)
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            b = pw.chromium.launch(headless=True, args=["--remote-debugging-port=9339"])
            hazir.set()
            bitti.wait(60)
            b.close()
    threading.Thread(target=sunucu, daemon=True).start()
    assert hazir.wait(30)
    monkeypatch.setattr(tr, "_cdp_adresi", lambda: ["http://127.0.0.1:9339"])
    try:
        t1 = tr.baglan()
        t2 = tr.baglan()
        assert t1.sayfa.context.browser is t2.sayfa.context.browser
        assert t1.sayfa is not t2.sayfa
        t1.kapat()  # gerçek Chrome'da hiçbir şey kapatmaz
        assert t2.sayfa.context.browser.is_connected()
    finally:
        tr.baglantiyi_kes()
        bitti.set()


def test_yerel_tarayici_ayari(monkeypatch):
    """Geliştirme/test için: SONDA_YEREL_TARAYICI ayarlıysa kullanıcının Chrome'u yerine Playwright Chromium'u açılır."""
    from sonda.tarayici import baglanti as tr
    monkeypatch.setenv("SONDA_YEREL_TARAYICI", "gizli")
    monkeypatch.setattr(tr, "_cdp_adresi", lambda: [])
    monkeypatch.setattr(tr, "CHROME", tr.Path("yok/chrome.exe"))  # yedek profil açılmasın
    try:
        t = tr.baglan()
        assert t.sayfa.context.browser.is_connected()
    finally:
        tr.baglantiyi_kes()


def test_acilir_pencere_kapaninca_onceki_sekmeye_doner(tarayici, site):
    tarayici.git(f"{site}/acilir.html")
    tarayici.tikla(bul(tarayici.bak(), "Pencere aç")["no"])
    import time
    son = time.monotonic() + 5  # pencere 300 ms sonra kendini kapatır; yüklü makinede gecikebilir
    while not tarayici.url.endswith("/acilir.html") and time.monotonic() < son:
        time.sleep(0.1)
    assert tarayici.url.endswith("/acilir.html")
    assert tarayici.bak()["baslik"] == "Açılır pencere"


def test_sekme_kapaninca_sekme_kapandi_hatasi(tarayici, site):
    from sonda.tarayici import baglanti as tr
    tarayici.git(f"{site}/giris.html")
    tarayici.sayfa.close()
    with pytest.raises(SekmeKapandi):
        tarayici.bak()


def test_metin_ekranda_gorunen_bolumu_verir_ve_kaydirinca_degisir(tarayici, site):
    tarayici.git(f"{site}/uzun.html")
    ust = tarayici.bak()
    assert "Bölüm 1 " in ust["metin"] and "Bölüm 25" not in ust["metin"]
    assert ust["kaydirma"]["y"] == 0 and ust["kaydirma"]["yukseklik"] > ust["kaydirma"]["ekran"] * 3
    for _ in range(20):
        tarayici.kaydir("asagi")
    alt = tarayici.bak()
    assert "Bölüm 30" in alt["metin"] and "Yorum 1" in alt["metin"] and "Bölüm 1 " not in alt["metin"]
    assert alt["kaydirma"]["y"] > 0


def test_daha_fazla_goster_butonu_icerik_acar(tarayici, site):
    tarayici.git(f"{site}/uzun.html")
    tarayici.tikla(bul(tarayici.bak(), "Daha fazla göster")["no"])
    assert "gizli yorum açıldı" in tarayici.bak()["metin"]



def test_ustu_kapali_butona_tiklama_engeli_soyler(tarayici, site):
    """Upwork'te görülen: tıklama zaman aşımı. Üstünde çerez/pop-up varsa model nedenini öğrenmeli."""
    from sonda.tarayici import TiklamaEngeli
    tarayici.git(f"{site}/engel.html")
    with pytest.raises(TiklamaEngeli) as h:
        tarayici.tikla(bul(tarayici.bak(), "Devam et")["no"])
    assert "Tümünü kabul et" in str(h.value) or "çerez" in str(h.value)
    tarayici.tikla(bul(tarayici.bak(), "Tümünü kabul et")["no"])
    tarayici.tikla(bul(tarayici.bak(), "Devam et")["no"])
    assert tarayici.sayfa.inner_text("#sonuc") == "Devam edildi"


def test_kaydirilan_alandaki_butona_tiklanir(tarayici, site):
    tarayici.git(f"{site}/engel.html")
    tarayici.sayfa.evaluate("document.getElementById('cerez').remove()")
    tarayici.tikla(bul(tarayici.bak(), "İçteki buton")["no"])
    assert tarayici.sayfa.inner_text("#sonuc") == "İçteki tıklandı"


def test_captcha_algilanir_ve_onay_kutusu_isaretlenir(tarayici, site):
    tarayici.git(f"{site}/captcha.html")
    assert tarayici.bak()["captcha"] is True
    assert tarayici.captcha_onayla() is True
    assert tarayici.sayfa.inner_text("#durum") == "Doğrulandı"
    assert tarayici.bak()["captcha"] is False


def test_captcha_olmayan_sayfa(tarayici, site):
    tarayici.git(f"{site}/giris.html")
    assert tarayici.bak()["captcha"] is False
    assert tarayici.captcha_onayla() is False



def test_kapali_shadow_dom_captcha_ekrandaki_yerinden_tiklanir(tarayici, site):
    """Cloudflare onay kutusu kapalı shadow DOM'da: seçiciyle bulunamaz, iframe'in ekrandaki yerine tıklanır."""
    tarayici.git(f"{site}/captcha_cf.html")
    assert tarayici.bak()["captcha"] is True
    assert tarayici.captcha_onayla() is True
    tarayici.sayfa.wait_for_timeout(300)
    assert tarayici.sayfa.inner_text("#durum") == "Doğrulandı"
    assert tarayici.bak()["captcha"] is False  # 0x0 görünmez reCAPTCHA çerçevesi captcha sayılmaz


def test_cloudflare_bekleme_ekrani_captcha_sayilir(tarayici, site):
    tarayici.git(f"{site}/bir_dakika.html")
    assert tarayici.bak()["captcha"] is True



# ---- Final inceleme I4: tıklama zaman aşımından sonra kör yeniden tıklama yok
def test_zaman_asimli_tiklama_tekrarlanmaz(tarayici, site):
    tarayici.git(f"{site}/yavas_tik.html")
    no = bul(tarayici.bak(), "Sepete ekle")["no"]
    try:
        tarayici.tikla(no)
    except Exception:
        pass
    tarayici.sayfa.wait_for_timeout(7000)
    assert tarayici.sayfa.evaluate("localStorage.getItem('tik')") == "1"


# ---- Final inceleme I5: captcha kılığındaki çerçeve altındaki butona tıklatamaz
def test_sahte_captcha_cercevesi_tiklatamaz(tarayici, site):
    from conftest import ihlaller
    tarayici.git(f"{site}/captcha_tuzak.html")
    tarayici.sayfa.wait_for_timeout(500)
    tarayici.captcha_onayla()
    tarayici.sayfa.wait_for_timeout(300)
    assert ihlaller(tarayici) == []


def test_captcha_adresi_alan_adina_gore_tanınır():
    from sonda.tarayici.sayfa import captcha_adresi_mi
    assert captcha_adresi_mi("https://challenges.cloudflare.com/cdn-cgi/challenge-platform/h/b/turnstile/if/ov2/")
    assert captcha_adresi_mi("https://www.google.com/recaptcha/api2/anchor?k=x")
    assert captcha_adresi_mi("https://newassets.hcaptcha.com/captcha/v1/abc/static/hcaptcha.html")
    assert not captcha_adresi_mi("https://evil.example/x?hcaptcha.com")
    assert not captcha_adresi_mi("https://evil.example/turnstile")
    assert not captcha_adresi_mi("https://www.google.com/search?q=recaptcha")



# ---- Final inceleme I3: sayfa ana dünyada DOM'u değiştirip korumayı kandıramaz
def test_yalanci_sayfa_korumayi_kandiramaz(tarayici, site):
    from sonda import koruma
    tarayici.git(f"{site}/yalanci.html")
    s = tarayici.bak()
    al = next(o for o in s["ogeler"] if o["kimlik"] == "al")
    kart = next(o for o in s["ogeler"] if o["kimlik"] == "kart")
    bilgi_al = tarayici.oge_bilgisi(al["no"])
    bilgi_kart = tarayici.oge_bilgisi(kart["no"])
    assert "Satın al" in bilgi_al["oge"]["metin"]
    assert not koruma.kontrol({"eylem": "tikla", "no": al["no"]}, bilgi_al["oge"], bilgi_al["form_ogeleri"]).izin
    assert bilgi_kart["oge"]["otomatik"] == "cc-number"
    assert not koruma.kontrol({"eylem": "yaz", "no": kart["no"], "metin": "4111"}, bilgi_kart["oge"]).izin


def test_golge_domdaki_ayni_numarali_tuzak(tarayici, site):
    from conftest import ihlaller
    tarayici.git(f"{site}/yalanci.html")
    no = next(o for o in tarayici.bak()["ogeler"] if o["kimlik"] == "yorum")["no"]
    tarayici.sayfa.evaluate("""n => {
        const kap = document.createElement('div'); document.body.prepend(kap);
        const kok = kap.attachShadow({ mode: 'open' });
        kok.innerHTML = `<button data-yasak data-sonda-id="${n}" onclick="ihlalEkle('tiklama', 'golge')">Öde</button>`;
    }""", no)
    assert tarayici.oge_bilgisi(no) is None  # aynı numara iki öğede: güvenilmez
    with pytest.raises(Exception):
        tarayici.tikla(no)
    assert ihlaller(tarayici) == []


# ---- Final inceleme I2: kilitlenen sayfa görev işçisini sonsuza dek bekletmez
def test_kilitli_sayfada_bak_zaman_asimina_ugrar(tarayici, site, monkeypatch):
    import time
    from sonda.tarayici import sayfa as sm
    monkeypatch.setattr(sm, "ZAMAN_ASIMI", 3000)
    tarayici.git(f"{site}/mesgul.html")
    time.sleep(0.8)  # sayfanın JS'i kilitlendi
    bas = time.monotonic()
    with pytest.raises(Exception):
        tarayici.bak()
    assert time.monotonic() - bas < 8


# ---- Upwork: gizli (sr-only) onay kutusu listelenmediği için contract-to-hire işaretlenemedi
def test_gizli_onay_kutusu_gorunen_etiketiyle_listelenir_ve_isaretlenir(tarayici, site):
    tarayici.git(f"{site}/gizli_onay.html")
    kutu = bul(tarayici.bak(), "contract-to-hire opportunities")
    assert kutu["tip"] == "checkbox" and kutu["secili"] is False
    tarayici.tikla(kutu["no"])
    assert tarayici.sayfa.is_checked("[name=c2h]")
    assert bul(tarayici.bak(), "contract-to-hire opportunities")["secili"] is True


def test_gizli_radyo_dugmesi_for_etiketiyle_listelenir(tarayici, site):
    tarayici.git(f"{site}/gizli_onay.html")
    s = tarayici.bak()
    az = bul(s, "Less than 30")
    assert az["tip"] == "radio" and az["secili"] is False and bul(s, "More than 30")["secili"] is True
    tarayici.tikla(az["no"])
    assert tarayici.sayfa.is_checked("#r2")
    assert len([o for o in s["ogeler"] if "More than 30" in o["metin"]]) == 1  # etiket bir kez listelenir
