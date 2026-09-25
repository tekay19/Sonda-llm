import pytest

import koruma


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
