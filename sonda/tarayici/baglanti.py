"""Kullanıcının Chrome'una CDP bağlantısı. Chrome her yeni bağlantıda izin istediği için bağlantı saklanır."""
import os
import subprocess
import time
from pathlib import Path

import httpx

from .sayfa import Tarayici


KOK = Path(__file__).resolve().parents[2]


YEDEK_PROFIL = KOK / "veri" / "chrome-profil"


YEDEK_PORT = 9223


CHROME = Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Google/Chrome/Application/chrome.exe"


class BaglantiHatasi(Exception):
    pass


def _cdp_adresi():
    dosya = Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/User Data/DevToolsActivePort"
    adresler = []
    if dosya.exists():
        satirlar = dosya.read_text().split("\n")
        if len(satirlar) >= 2 and satirlar[0].strip().isdigit():
            adresler.append(f"ws://127.0.0.1:{satirlar[0].strip()}{satirlar[1].strip()}")
    try:
        httpx.get(f"http://127.0.0.1:{YEDEK_PORT}/json/version", timeout=1)
        adresler.append(f"http://127.0.0.1:{YEDEK_PORT}")
    except httpx.HTTPError:
        pass
    return adresler


def _yedek_profili_ac():
    YEDEK_PROFIL.mkdir(parents=True, exist_ok=True)
    subprocess.Popen([str(CHROME), f"--user-data-dir={YEDEK_PROFIL}", f"--remote-debugging-port={YEDEK_PORT}",
                      "--no-first-run", "--no-default-browser-check"])
    for _ in range(30):
        time.sleep(0.5)
        try:
            httpx.get(f"http://127.0.0.1:{YEDEK_PORT}/json/version", timeout=1)
            return f"http://127.0.0.1:{YEDEK_PORT}"
        except httpx.HTTPError:
            continue
    return None


BAGLANTI_YARDIMI = ("Chrome'a bağlanamadım. Chrome'da adres çubuğuna chrome://inspect/#remote-debugging yazıp "
                    "uzaktan hata ayıklama anahtarını aç. Chrome izin sorarsa (Sonda'nın ilk görevinde bir kez) "
                    "\"İzin ver\"e bas, sonra görevi tekrar ver.")


# (playwright, browser): Chrome her yeni CDP bağlantısında kullanıcıdan izin istediği için bağlantı sunucu ömrü
# boyunca saklanır. Playwright nesneleri iş parçacığına bağlıdır: baglan() hep aynı iş parçacığından çağrılmalı
# (gorev._ISCI).
_baglanti = None


def baglan():
    """Kullanıcının Chrome'una bağlanır (varsa mevcut bağlantıyı kullanır) ve yeni bir sekme açar."""
    global _baglanti
    if _baglanti is None or not _baglanti[1].is_connected():
        baglantiyi_kes()
        _baglanti = _yeni_baglanti()
    b = _baglanti[1]
    baglam = b.contexts[0] if b.contexts else b.new_context()
    return Tarayici(baglam.new_page())  # kapat=None: sekme ve kullanıcının Chrome'u açık kalır


def baglantiyi_kes():
    global _baglanti
    if _baglanti:
        try:
            _baglanti[0].stop()  # browser.close() değil: kullanıcının Chrome'u kapanmasın
        except Exception:
            pass
    _baglanti = None


def _yeni_baglanti():
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    yerel = os.environ.get("SONDA_YEREL_TARAYICI")  # geliştirme/test: "gizli" ya da "acik"
    if yerel:
        return pw, pw.chromium.launch(headless=yerel == "gizli")
    adresler = _cdp_adresi()
    if not adresler and CHROME.exists():
        yedek = _yedek_profili_ac()
        adresler = [yedek] if yedek else []
    for adres in adresler:
        try:
            return pw, pw.chromium.connect_over_cdp(adres, timeout=90000)
        except Exception:
            continue
    pw.stop()
    raise BaglantiHatasi(BAGLANTI_YARDIMI)
