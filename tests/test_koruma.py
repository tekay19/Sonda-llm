import pytest

from sonda import koruma


def oge(**k):
    temel = {"no": 1, "etiket": "input", "rol": "", "tip": "text", "ad": "", "kimlik": "", "otomatik": "",
             "yer": "", "aria": "", "baslik": "", "metin": "", "deger": "", "href": "", "form": -1,
             "form_eylem": "", "ekranda": True}
    temel.update(k)
    return temel


def buton(metin, **k):
    return oge(etiket="button", tip=k.pop("tip", "button"), metin=metin, **k)


# ---- hassas alanlar
@pytest.mark.parametrize("alan", [
    oge(tip="password"),
    oge(otomatik="cc-number"), oge(otomatik="cc-csc"), oge(otomatik="cc-exp"),
    oge(otomatik="current-password"), oge(otomatik="new-password"), oge(otomatik="one-time-code"),
    oge(metin="Kart Numarası"), oge(metin="KART NUMARASI"), oge(ad="cardNumber"), oge(ad="card_number"),
    oge(yer="CVV"), oge(kimlik="cvc"), oge(metin="Güvenlik Kodu"), oge(metin="Son Kullanma Tarihi"),
    oge(ad="expMonth"), oge(ad="expiry"), oge(metin="IBAN"), oge(metin="Şifre"), oge(metin="ŞİFRE"),
    oge(metin="Parola"), oge(metin="PIN"), oge(ad="otp"), oge(metin="Doğrulama Kodu"),
    oge(metin="SMS kodu"), oge(aria="Verification code"), oge(ad="cc-number"),
])
def test_hassas_alanlar_taninir(alan):
    assert koruma.hassas_alan(alan)


@pytest.mark.parametrize("alan", [
    oge(metin="Ad Soyad"), oge(ad="email", tip="email"), oge(metin="Telefon"), oge(metin="Adres"),
    oge(ad="q", tip="search"), oge(metin="Shopping"), oge(metin="Spinner"), oge(metin="Kargo notu"),
])
def test_normal_alanlar_hassas_degil(alan):
    assert not koruma.hassas_alan(alan)


def test_arama_kutusundaki_kart_kelimesi_hassas_sayilmaz():
    assert not koruma.hassas_alan(oge(tip="search", yer="Hediye kartı ara"))


def test_arama_kutusu_olsa_da_sifre_tipi_hassastir():
    assert koruma.hassas_alan(oge(tip="password", ad="q"))


def test_yaniltici_etiketli_kart_alani():
    assert koruma.hassas_alan(oge(metin="Kupon kodu", otomatik="cc-number"))
    assert koruma.hassas_alan(oge(metin="Not", yer="Kart numarası"))


def test_hassas_alana_yazma_engellenir():
    k = koruma.kontrol({"eylem": "yaz", "no": 1, "metin": "4111"}, oge(metin="Kart Numarası"))
    assert not k.izin and "sen" in k.sebep


def test_hassas_secim_engellenir():
    k = koruma.kontrol({"eylem": "sec", "no": 1, "deger": "12"}, oge(etiket="select", tip="", ad="expMonth"))
    assert not k.izin


def test_normal_alana_yazma_izinli():
    assert koruma.kontrol({"eylem": "yaz", "no": 1, "metin": "Semih"}, oge(metin="Ad Soyad")).izin


# ---- yasak butonlar
@pytest.mark.parametrize("metin", [
    "Öde", "ÖDE", "Öde 499 TL", "Ödeme Yap", "Ödemeyi Tamamla", "Ödemeye Geç", "Satın Al", "SATIN AL",
    "Hemen Al", "Siparişi Onayla", "Siparişi Tamamla", "Sipariş Ver", "Gönder", "Başvur",
    "Başvuruyu Gönder", "Sil", "Kaldır", "Hesabı Kapat", "Onayla", "Giriş Yap", "Oturum Aç", "Üye Ol",
    "Kayıt Ol", "Abone Ol", "Pay", "Pay now", "Buy now", "Purchase", "Place order", "Checkout",
    "Check out", "Submit", "Send", "Apply", "Delete", "Remove", "Confirm", "Sign in", "Log in",
    "Login", "Sign up", "Register", "Subscribe",
])
def test_yasak_butonlar_engellenir(metin):
    k = koruma.kontrol({"eylem": "tikla", "no": 1}, buton(metin))
    assert not k.izin, metin


@pytest.mark.parametrize("metin", [
    "Ara", "Google'da Ara", "Sepete Ekle", "Sepete Git", "Kabul Et", "Tümünü kabul et", "Devam",
    "Sonraki", "Filtrele", "Fiyata göre sırala", "Episode 3", "Kod örnekleri", "Blog", "Payment options info",
])
def test_normal_butonlar_izinli(metin):
    assert koruma.kontrol({"eylem": "tikla", "no": 1}, buton(metin)).izin, metin


def test_yasak_kelime_aria_veya_degerde_de_yakalanir():
    assert koruma.yasak_buton(buton("→", aria="Ödemeyi tamamla"))
    assert koruma.yasak_buton(oge(etiket="input", tip="submit", deger="Satın al"))


def test_hassas_formdaki_submit_butonu_engellenir():
    gonder = buton("Devam", tip="submit", form=0)
    sifre = oge(tip="password", form=0)
    k = koruma.kontrol({"eylem": "tikla", "no": 1}, gonder, [sifre])
    assert not k.izin


def test_tipsiz_form_butonu_submit_sayilir():
    k = koruma.kontrol({"eylem": "tikla", "no": 1}, buton("İleri", tip="", form=0), [oge(otomatik="cc-number", form=0)])
    assert not k.izin


def test_hassas_olmayan_formdaki_submit_izinli():
    k = koruma.kontrol({"eylem": "tikla", "no": 1}, buton("Devam", tip="submit", form=0), [oge(metin="Ad Soyad", form=0)])
    assert k.izin


# ---- Enter kuralı
@pytest.mark.parametrize("alan", [
    oge(tip="search"), oge(rol="searchbox"), oge(etiket="textarea", tip="", ad="q"), oge(ad="query"),
    oge(ad="search"), oge(ad="k"), oge(form=0, form_eylem="/ara"), oge(form=0, form_eylem="https://x.com/search"),
])
def test_enter_arama_kutusunda_izinli(alan):
    k = koruma.kontrol({"eylem": "yaz", "no": 1, "metin": "ssd", "enter": True}, alan)
    assert k.izin and k.enter


@pytest.mark.parametrize("alan", [oge(ad="email", tip="email"), oge(metin="Ad Soyad"), oge(form=0, form_eylem="/basvuru")])
def test_enter_diger_alanlarda_yok_sayilir(alan):
    k = koruma.kontrol({"eylem": "yaz", "no": 1, "metin": "x", "enter": True}, alan)
    assert k.izin and not k.enter


def test_enter_istenmediyse_basilmaz():
    assert not koruma.kontrol({"eylem": "yaz", "no": 1, "metin": "ssd"}, oge(tip="search")).enter


# ---- adresler
@pytest.mark.parametrize("url", ["https://www.google.com/search?q=a", "http://localhost:8000/x"])
def test_http_adresleri_izinli(url):
    assert koruma.kontrol({"eylem": "git", "url": url}).izin


@pytest.mark.parametrize("url", ["javascript:alert(1)", "file:///C:/Windows", "chrome://settings", "about:blank", ""])
def test_diger_semalar_engellenir(url):
    assert not koruma.kontrol({"eylem": "git", "url": url}).izin


def test_diger_eylemler_izinli():
    for e in ("kaydir", "geri", "bak", "oku", "not_al", "bitir", "sana_birak"):
        assert koruma.kontrol({"eylem": e}).izin


def test_sade_turkce_harfleri_duzlestirir():
    assert koruma.sade("ÖDEME Yapİ-ş_ĞÜ") == "odeme yapi s gu"
    assert koruma.sade("cardNumber") == "card number"


# Kullanıcı kararı (25 Eylül): profil düzenlemede kaydetme butonlarına Sonda kendisi basar.
@pytest.mark.parametrize("metin", ["Save", "Kaydet", "Değişiklikleri kaydet", "Güncelle", "Update", "Save changes",
                                   "Edit", "Düzenle"])
def test_kaydetme_butonlari_izinli(metin):
    assert koruma.kontrol({"eylem": "tikla", "no": 1}, buton(metin)).izin, metin


# ---- Kullanıcı kararı (25 Eylül): görevde verilen şifre, adı geçen sitede girilebilir
GOREV = "upwork hesabıma gir: e-posta semih@ornek.com, şifrem Gizli.Sifre-42 ve profilimi incele"
UPWORK = "https://www.upwork.com/ab/account-security/login"


def test_gorevde_verilen_sifre_adi_gecen_sitede_yazilabilir():
    k = koruma.kontrol({"eylem": "yaz", "no": 1, "metin": "Gizli.Sifre-42"}, oge(tip="password", metin="Password"),
                       gorev_metni=GOREV, url=UPWORK)
    assert k.izin


def test_gorevde_olmayan_sifre_yazilamaz():
    k = koruma.kontrol({"eylem": "yaz", "no": 1, "metin": "baska-sifre"}, oge(tip="password"),
                       gorev_metni=GOREV, url=UPWORK)
    assert not k.izin


def test_sifre_baska_sitede_yazilamaz():
    k = koruma.kontrol({"eylem": "yaz", "no": 1, "metin": "Gizli.Sifre-42"}, oge(tip="password"),
                       gorev_metni=GOREV, url="https://upwork-login.evil.com/login")
    assert not k.izin


@pytest.mark.parametrize("alan", [oge(otomatik="cc-number"), oge(metin="CVV"), oge(metin="IBAN"),
                                  oge(otomatik="one-time-code"), oge(metin="SMS kodu")])
def test_gorevde_verilse_de_kart_ve_kod_alanlari_kullanicida(alan):
    gorev_ = "upwork kartım 4111111111111111 cvv 123 kod 998877 iban TR00"
    for deger in ("4111111111111111", "123", "998877", "TR00"):
        assert not koruma.kontrol({"eylem": "yaz", "no": 1, "metin": deger}, alan, gorev_metni=gorev_, url=UPWORK).izin


def test_kisa_sifre_parcasi_kabul_edilmez():
    k = koruma.kontrol({"eylem": "yaz", "no": 1, "metin": "Gi"}, oge(tip="password"), gorev_metni=GOREV, url=UPWORK)
    assert not k.izin


@pytest.mark.parametrize("metin", ["Log in", "Giriş Yap", "Sign in", "Continue with password"])
def test_kimlik_verilen_gorevde_giris_butonu_izinli(metin):
    assert koruma.kontrol({"eylem": "tikla", "no": 1}, buton(metin), gorev_metni=GOREV, url=UPWORK).izin


def test_kimlik_verilen_gorevde_giris_formu_submit_izinli():
    k = koruma.kontrol({"eylem": "tikla", "no": 1}, buton("Continue", tip="submit", form=0), [oge(tip="password", form=0)],
                       gorev_metni=GOREV, url=UPWORK)
    assert k.izin


def test_kimlik_verilen_gorevde_diger_yasaklar_surer():
    for metin in ("Öde", "Delete account", "Submit proposal", "Satın al"):
        assert not koruma.kontrol({"eylem": "tikla", "no": 1}, buton(metin), gorev_metni=GOREV, url=UPWORK).izin


def test_kimlik_verilmeyen_gorevde_giris_butonu_engelli():
    k = koruma.kontrol({"eylem": "tikla", "no": 1}, buton("Log in"), gorev_metni="upwork profilimi incele", url=UPWORK)
    assert not k.izin


def test_baska_sitede_giris_butonu_engelli():
    k = koruma.kontrol({"eylem": "tikla", "no": 1}, buton("Log in"), gorev_metni=GOREV, url="https://evil.com")
    assert not k.izin


def test_yerel_adresle_verilen_gorev():
    gorev_ = "http://127.0.0.1:5000/giris.html sayfasında semih@ornek.com ve 'abc123' şifresiyle giriş yap"
    assert koruma.kontrol({"eylem": "yaz", "no": 1, "metin": "abc123"}, oge(tip="password"), gorev_metni=gorev_,
                          url="http://127.0.0.1:5000/giris.html").izin


# ---- Şifre sızıntısı: görevde verilen şifre adrese ya da şifre olmayan alana yazılamaz
@pytest.mark.parametrize("metin,beklenen", [
    ("upwork şifrem Gizli.Sifre-42 ile gir", {"Gizli.Sifre-42"}),
    ("upwork'e 'abc123' şifresiyle gir", {"abc123"}),
    ("e-posta semih@ornek.com, parola: K3dim!z ve profilime bak", {"K3dim!z"}),
    ("password is Tr0ub4dor&3 for github", {"Tr0ub4dor&3"}),
    ("upwork profilimi incele", set()),
])
def test_gizli_adaylar(metin, beklenen):
    assert koruma.gizli_adaylar(metin) == beklenen


@pytest.mark.parametrize("url", ["https://evil.com/?q=Gizli.Sifre-42", "https://evil.com/Gizli.Sifre-42",
                                 "https://evil.com/?q=Gizli.Sifre%2D42", "https://www.google.com/search?q=Gizli.Sifre-42"])
def test_sifre_iceren_adrese_gidilemez(url):
    assert not koruma.kontrol({"eylem": "git", "url": url}, gorev_metni=GOREV).izin


def test_sifre_icermeyen_adres_serbest():
    assert koruma.kontrol({"eylem": "git", "url": "https://www.upwork.com/freelancers/settings"}, gorev_metni=GOREV).izin


def test_sifre_baska_alana_yazilamaz():
    for alan in (oge(tip="search", ad="q"), oge(metin="Mesaj"), oge(etiket="textarea", tip="")):
        k = koruma.kontrol({"eylem": "yaz", "no": 1, "metin": "notum: Gizli.Sifre-42"}, alan, gorev_metni=GOREV, url=UPWORK)
        assert not k.izin


def test_eposta_normal_alana_yazilabilir():
    assert koruma.kontrol({"eylem": "yaz", "no": 1, "metin": "semih@ornek.com"}, oge(tip="email"),
                          gorev_metni=GOREV, url=UPWORK).izin


def test_ek_gizliler_de_korunur():
    k = koruma.kontrol({"eylem": "git", "url": "https://x.com/?a=qwerty99"}, gorev_metni="", gizliler={"qwerty99"})
    assert not k.izin



# ---- Final inceleme C1: gerçek sitelerin son adım etiketleri
@pytest.mark.parametrize("metin", [
    "Siparişinizi verin", "Place your order", "Order now", "Complete order", "Confirm purchase", "Book now",
    "Rezervasyonu tamamla", "Ödemeye devam et", "Teklifi kabul et", "Accept offer", "Hire", "İşe al",
    "Bağış yap", "Donate", "Transfer et", "Havale yap", "Para gönder", "Send money", "Complete booking",
])
def test_gercek_son_adim_etiketleri_engellenir(metin):
    assert koruma.yasak_buton(buton(metin)), metin


@pytest.mark.parametrize("metin", ["Kabul Et", "Tümünü kabul et", "Accept all cookies", "Sepete Ekle", "Kaydet",
                                   "Siparişlerim", "Order history", "Booking.com"])
def test_benzer_ama_zararsiz_etiketler_serbest(metin):
    assert not koruma.yasak_buton(buton(metin)), metin


@pytest.mark.parametrize("url", ["https://www.amazon.com.tr/gp/buy/spc/handlers/display.html",
                                 "https://www.trendyol.com/odeme", "https://shop.example.com/checkout/review"])
def test_odeme_sayfasinda_devam_butonu_engellenir(url):
    for metin in ("Devam", "Continue", "İleri", "Proceed"):
        assert not koruma.kontrol({"eylem": "tikla", "no": 1}, buton(metin), url=url).izin, (url, metin)


def test_odeme_sayfasi_disinda_devam_serbest():
    assert koruma.kontrol({"eylem": "tikla", "no": 1}, buton("Devam"), url="https://www.upwork.com/nx/find-work/").izin


# ---- Final inceleme C2: şifre yalnızca gerçekten adı geçen sitede
@pytest.mark.parametrize("url", ["https://upwork.xyz/login", "https://upwork.net/login", "https://www.upwork.ru/giris",
                                 "https://upwork.com.evil.io/login"])
def test_sifre_benzer_alan_adinda_yazilamaz(url):
    k = koruma.kontrol({"eylem": "yaz", "no": 1, "metin": "Gizli.Sifre-42"}, oge(tip="password"), gorev_metni=GOREV, url=url)
    assert not k.izin, url


def test_sifre_ayni_markanin_baska_alt_alanina_yazilamaz():
    gorev_ = "google hesabıma gir, şifrem Abc12345!"
    assert not koruma.kontrol({"eylem": "yaz", "no": 1, "metin": "Abc12345!"}, oge(tip="password"), gorev_metni=gorev_,
                              url="https://docs.google.com/forms/d/e/x/viewform").izin
    assert koruma.kontrol({"eylem": "yaz", "no": 1, "metin": "Abc12345!"}, oge(tip="password"), gorev_metni=gorev_,
                          url="https://accounts.google.com/signin").izin


def test_gorevde_yazan_alan_adi_esas_alinir():
    gorev_ = "e-devlet (turkiye.gov.tr) şifrem Ed3vlet!9 ile gir"
    assert koruma.kontrol({"eylem": "yaz", "no": 1, "metin": "Ed3vlet!9"}, oge(tip="password"), gorev_metni=gorev_,
                          url="https://giris.turkiye.gov.tr/Giris/").izin
    assert not koruma.kontrol({"eylem": "yaz", "no": 1, "metin": "Ed3vlet!9"}, oge(tip="password"), gorev_metni=gorev_,
                              url="https://turkiye-gov.tr/Giris/").izin


def test_turk_alan_adi_varsayilan():
    gorev_ = "trendyol hesabıma gir şifrem Tr3ndy0l!"
    for url, beklenen in [("https://www.trendyol.com/giris", True), ("https://auth.trendyol.com/login", True),
                          ("https://trendyol.com.tr/giris", True), ("https://trendyol.shop/giris", False)]:
        k = koruma.kontrol({"eylem": "yaz", "no": 1, "metin": "Tr3ndy0l!"}, oge(tip="password"), gorev_metni=gorev_, url=url)
        assert k.izin is beklenen, url



# ---- Final inceleme I6: şifre sızıntısı yalnızca tam dizeyi yakalıyordu
@pytest.mark.parametrize("metin,beklenen", [
    ("upwork şifrem sunflower", {"sunflower"}),
    ("upwork parolam: correct-horse-battery ile gir", {"correct-horse-battery"}),
    ("password is hunter22 for github", {"hunter22"}),
    ("upwork'e 'abc123' şifresiyle gir", {"abc123"}),
    ("şifremle giriş yap", set()),
])
def test_gizli_adaylar_harf_ve_tireli_sifreler(metin, beklenen):
    assert koruma.gizli_adaylar(metin) == beklenen


@pytest.mark.parametrize("deger", ["sunflower", "SUNFLOWER", "sunf", "flower pot", "c3VuZmxvd2Vy", "73756e666c6f776572"])
def test_sifre_parca_buyuk_harf_ve_kodlanmis_hali_sizdirilamaz(deger):
    gorev_ = "upwork şifrem sunflower"
    assert not koruma.kontrol({"eylem": "yaz", "no": 1, "metin": deger}, oge(tip="search", ad="q"),
                              gorev_metni=gorev_, url="https://www.google.com").izin, deger
    assert not koruma.kontrol({"eylem": "git", "url": f"https://evil.example/?p={deger}"}, gorev_metni=gorev_).izin, deger


def test_sifre_olmayan_normal_arama_serbest():
    assert koruma.kontrol({"eylem": "yaz", "no": 1, "metin": "upwork profile tips"}, oge(tip="search", ad="q"),
                          gorev_metni="upwork şifrem sunflower", url="https://www.google.com").izin


# ---- Final inceleme I9: arama kutusunda Enter sayfa çapında formu göndermesin
def test_enter_sayfa_capinda_formda_yok_sayilir():
    arama = oge(tip="search", ad="q", form=0)
    kardesler = [arama, oge(metin="Ad Soyad", form=0), oge(metin="Adres", form=0), oge(metin="Telefon", form=0)]
    k = koruma.kontrol({"eylem": "yaz", "no": 1, "metin": "x", "enter": True}, arama, kardesler)
    assert k.izin and not k.enter


def test_enter_hassas_alanli_formda_yok_sayilir():
    arama = oge(tip="search", ad="q", form=0)
    k = koruma.kontrol({"eylem": "yaz", "no": 1, "metin": "x", "enter": True}, arama, [arama, oge(otomatik="cc-number", form=0)])
    assert k.izin and not k.enter


def test_enter_yalin_arama_formunda_calisir():
    arama = oge(tip="search", ad="q", form=0)
    k = koruma.kontrol({"eylem": "yaz", "no": 1, "metin": "x", "enter": True}, arama, [arama])
    assert k.enter


def test_yer_tutucular_sirayla():
    h = koruma.yer_tutucular("upwork.com şifrem Gizli-7788, gmail şifresi abc!12345 olsun")
    assert h == {"{SIFRE_1}": "Gizli-7788", "{SIFRE_2}": "abc!12345"}


def test_yer_tut_metni_degistirir():
    h = {"{SIFRE_1}": "Parola-7788"}
    assert koruma.yer_tut("şifrem Parola-7788 ile gir, parola-7788", h) == "şifrem {SIFRE_1} ile gir, {SIFRE_1}"


def test_sifre_yoksa_bos_harita():
    assert koruma.yer_tutucular("en ucuz ssd'yi bul") == {}


# ---- Final inceleme: kullanıcı adı şifre yer tutucusu sanılmasın
def test_yer_tutucu_yalnizca_sifre_sozcugunden_sonraki_deger():
    assert koruma.yer_tutucular("instagram.com a gir kullanıcı ali_99 şifre Kedi-1234") == {"{SIFRE_1}": "Kedi-1234"}


def test_yer_tutucu_sozcukten_once_gelen_sifre():
    assert koruma.yer_tutucular("upwork.com'a 'abc12345' şifresiyle gir") == {"{SIFRE_1}": "abc12345"}


def test_parola_iceren_sifreden_sonraki_kelime_sifre_sayilmaz():
    """'Parola-7788' şifrenin kendisi; ardından gelen 'gmail' şifre değil."""
    assert koruma.gizli_adaylar("upwork.com şifrem Parola-7788, gmail şifresi abc!12345") == {"Parola-7788", "abc!12345"}
