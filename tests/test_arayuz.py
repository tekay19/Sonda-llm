"""Arayüzün görev modu olaylarını doğru gösterdiğini gerçek tarayıcıda sınar (sunucu akışı sahte)."""
import socket
import tempfile
import threading
import time
from pathlib import Path

import pytest
import uvicorn

from sonda import asistan, gorev, sunucu

KOMUTLAR = []
SERBESTLER = []  # her isteğin "butonlara kendisi bassın" değeri


def _sahte_akis(senaryo):
    def calistir(soru, gecmis, model, mod, *a, **k):
        SERBESTLER.append(k.get("serbest"))
        yield from senaryo(soru)
    return calistir


def _gorev_senaryosu(soru):
    if "teşekkür" in soru:
        yield {"tur": "yon", "hedef": "sohbet"}
        yield {"tur": "token", "metin": "Rica ederim!"}
        yield {"tur": "bitti", "sure": 2.0}
        return
    yield {"tur": "yon", "hedef": "gorev"}
    yield {"tur": "gorev_basladi", "id": "g1"}
    yield {"tur": "adim", "tip": "gezin", "metin": "hepsiburada.com açıldı"}
    yield {"tur": "anlatim", "metin": "Hepsiburada'da arıyorum."}
    if "durdur" in soru:
        for _ in range(100):  # arayüz "durdur" gönderene kadar bekle
            if ("g1", "durdur") in KOMUTLAR:
                break
            time.sleep(0.05)
        yield {"tur": "gorev_bitti", "durum": "durduruldu"}
        yield {"tur": "token", "metin": "O ana kadar 3.199 TL bulundu."}
    else:
        yield {"tur": "anlatim", "metin": "3.199 TL buldum."}
        yield {"tur": "gorev_bitti", "durum": "tamamlandi"}
        yield {"tur": "token", "metin": "En ucuz 3.199 TL."}
    yield {"tur": "bitti", "sure": 75.0}


@pytest.fixture(scope="module")
def arayuz():
    mp = pytest.MonkeyPatch()
    mp.setattr(sunucu, "calistir", _sahte_akis(_gorev_senaryosu))
    mp.setattr(gorev, "komut_ver", lambda gid, komut: KOMUTLAR.append((gid, komut)) or True)
    from sonda import ayarlar
    from sonda.model import ModelHatasi, gemini_saglayici
    mp.setattr(ayarlar, "DOSYA", Path(tempfile.mkdtemp()) / "ayarlar.json")  # gerçek anahtara dokunulmaz
    mp.delenv("GEMINI_API_KEY", raising=False)

    def dogrula(a):
        if a == "YANLIS":
            raise ModelHatasi("Gemini anahtarı geçersiz ya da yetkisiz. Ayarlar'dan kontrol et.")
    mp.setattr(gemini_saglayici, "anahtar_dogrula", dogrula)
    mp.setattr(gemini_saglayici, "modeller",
               lambda: [{"ad": "gemini:gemini-flash-latest", "etiket": "Gemini Flash (bulut, ucuz ve akıllı)"}]
               if ayarlar.gemini_anahtari() else [])
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    sunucu_ = uvicorn.Server(uvicorn.Config(sunucu.app, host="127.0.0.1", port=port, log_level="error"))
    threading.Thread(target=sunucu_.run, daemon=True).start()
    while not sunucu_.started:
        time.sleep(0.05)
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    b = pw.chromium.launch()
    yield b, f"http://127.0.0.1:{port}"
    b.close()
    pw.stop()
    sunucu_.should_exit = True
    mp.undo()


def _sayfa(arayuz):
    b, adres = arayuz
    s = b.new_page()
    s.goto(adres)
    s.evaluate("localStorage.clear()")
    s.reload()
    s.wait_for_selector("#model option:not([value=''])", state="attached")  # kurulu gerçek modeller listelenir
    s.click("[data-mod=gorev]")
    return s


def _gonder(s, metin):
    s.fill("#soru", metin)
    s.press("#soru", "Enter")


def test_gorev_anlatim_ve_bitis_satiri(arayuz):
    s = _sayfa(arayuz)
    _gonder(s, "fiyat karşılaştır")
    s.wait_for_selector(".durum-satiri.tamam")
    assert [x for x in s.inner_text(".anlatim").splitlines() if x] == ["Hepsiburada'da arıyorum.", "3.199 TL buldum."]
    assert "Görev tamamlandı" in s.inner_text(".durum-satiri") and "1 dk 15 sn" in s.inner_text(".durum-satiri")
    assert s.get_attribute("#soru", "placeholder") == "Devam et ya da yeni bir görev ver"
    s.close()


def test_sohbet_yonlendirmesi_etiketi(arayuz):
    s = _sayfa(arayuz)
    _gonder(s, "teşekkürler")
    s.wait_for_selector(".durum-satiri")
    assert "Tarayıcı açılmadan" in s.inner_text(".durum-satiri")
    assert "Rica ederim!" in s.inner_text(".cevap")
    s.close()


def test_durdur_baglantiyi_kesmez_ozet_gelir(arayuz):
    KOMUTLAR.clear()
    s = _sayfa(arayuz)
    _gonder(s, "uzun görev durdur")
    s.wait_for_selector(".anlatim")
    s.click("#gonder")  # çalışırken gönder butonu "Durdur" olur
    s.wait_for_selector(".durum-satiri.uyari")
    assert ("g1", "durdur") in KOMUTLAR
    assert "O ana kadar 3.199 TL bulundu." in s.inner_text(".cevap")
    assert "Durduruldu" not in s.inner_text(".cevap")
    assert "Görev durduruldu" in s.inner_text(".durum-satiri")
    s.close()


def test_ayarlar_gemini_anahtari(arayuz):
    s = _sayfa(arayuz)
    s.click("#ayarlar-ac")
    s.fill("#gemini-anahtar", "YANLIS")
    s.click("[data-gemini-kaydet]")
    s.wait_for_selector(".ayar-durum.hata")
    assert "geçersiz" in s.inner_text(".ayar-durum")
    s.fill("#gemini-anahtar", "AIzaDOGRUabcd")
    s.click("[data-gemini-kaydet]")
    s.wait_for_selector(".ayar-durum.tamam")
    govde = s.inner_text("#cekmece-govde")
    assert "…abcd" in govde and "DOGRU" not in govde and "Google" in govde  # gizlilik notu
    s.wait_for_selector("#model option[value='gemini:gemini-flash-latest']", state="attached")
    assert "(bulut" in s.inner_text("#model")
    s.click("[data-gemini-sil]")
    s.wait_for_function("!document.querySelector(\"#model option[value='gemini:gemini-flash-latest']\")")
    s.close()


def test_ayarlar_paneli_hafiza_yenilemesiyle_ezilmez(arayuz):
    s = _sayfa(arayuz)
    s.click("#ayarlar-ac")
    s.wait_for_selector("#gemini-anahtar")
    s.evaluate("hafizaCiz()")  # cevap sonrası arka planda çağrılır
    s.wait_for_timeout(300)
    assert s.inner_text("#cekmece-baslik") == "Ayarlar"
    s.close()


def test_bulut_model_secilince_gizlilik_rozeti_degisir(arayuz):
    s = _sayfa(arayuz)
    s.click("#ayarlar-ac")
    s.fill("#gemini-anahtar", "AIzaDOGRUabcd")
    s.click("[data-gemini-kaydet]")
    s.wait_for_selector("#model option[value='gemini:gemini-flash-latest']", state="attached")
    s.select_option("#model", "gemini:gemini-flash-latest")
    assert "Google" in s.inner_text(".yerel-rozet") and "bu bilgisayarda çalışır" not in s.inner_text(".yerel-rozet")
    yerel = s.eval_on_selector("#model option:not([value^='gemini:'])", "o => o.value")
    s.select_option("#model", yerel)
    assert "Model bu bilgisayarda çalışır" in s.inner_text(".yerel-rozet")
    s.click("[data-gemini-sil]")
    s.close()


def test_serbest_kutucugu_yalniz_gorevde_gorunur_ve_istekle_gider(arayuz):
    s = _sayfa(arayuz)
    assert s.is_visible("#serbest") and not s.is_checked("#serbest")
    _gonder(s, "fiyat karşılaştır")
    s.wait_for_selector(".durum-satiri.tamam")
    assert SERBESTLER[-1] is False
    s.check("#serbest")
    _gonder(s, "fiyat karşılaştır yine")
    s.wait_for_function("document.querySelectorAll('.durum-satiri.tamam').length === 2")
    assert SERBESTLER[-1] is True
    s.click("[data-mod=hizli]")
    assert not s.is_visible("#serbest-kutu")
    s.close()
