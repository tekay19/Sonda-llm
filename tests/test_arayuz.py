"""Arayüzün görev modu olaylarını doğru gösterdiğini gerçek tarayıcıda sınar (sunucu akışı sahte)."""
import socket
import threading
import time

import pytest
import uvicorn

from sonda import asistan, gorev, sunucu

KOMUTLAR = []


def _sahte_akis(senaryo):
    def calistir(soru, gecmis, model, mod, *a, **k):
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
