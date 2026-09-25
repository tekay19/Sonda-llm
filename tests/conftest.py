import functools
import http.server
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SAYFALAR = Path(__file__).resolve().parent / "sayfalar"


class _SessizIsleyici(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


@pytest.fixture(scope="session")
def site():
    """tests/sayfalar klasörünü rastgele bir portta sunar; kök adresi döner."""
    isleyici = functools.partial(_SessizIsleyici, directory=str(SAYFALAR))
    sunucu = http.server.ThreadingHTTPServer(("127.0.0.1", 0), isleyici)
    threading.Thread(target=sunucu.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{sunucu.server_address[1]}"
    sunucu.shutdown()


@pytest.fixture
def yerel_tarayici_ac():
    """Playwright'ın kendi Chromium'unda Tarayici açan fonksiyon (kullanıcının Chrome'una dokunmaz).
    Playwright'ın senkron API'si iş parçacığına bağlı olduğundan, fonksiyon onu kullanacak iş parçacığında çağrılmalıdır."""
    from playwright.sync_api import sync_playwright

    from sonda.tarayici import Tarayici

    def ac():
        pw = sync_playwright().start()
        b = pw.chromium.launch(headless=True)
        sayfa = b.new_context(viewport={"width": 1280, "height": 900}).new_page()
        return Tarayici(sayfa, kapat=lambda: (b.close(), pw.stop()))
    return ac


@pytest.fixture
def tarayici(yerel_tarayici_ac):
    t = yerel_tarayici_ac()
    yield t
    t.kapat()


def ihlaller(t):
    """Test sayfalarının localStorage'a yazdığı güvenlik ihlalleri."""
    return t.sayfa.evaluate("JSON.parse(localStorage.getItem('ihlaller') || '[]')")


@pytest.fixture(autouse=True, scope="session")
def _gecici_gorev_kayitlari(tmp_path_factory):
    """Görev hata ayıklama kayıtları testlerde geçici klasöre gider (gerçek kayıtlar silinmesin)."""
    from sonda.gorev import ayar
    eski = ayar.KAYIT_KLASORU
    ayar.KAYIT_KLASORU = tmp_path_factory.mktemp("gorev_kayitlari")
    yield
    ayar.KAYIT_KLASORU = eski


@pytest.fixture(autouse=True, scope="session")
def _test_captcha_ana_makinesi():
    """Testlerde yerel sahte captcha çerçeveleri localhost'tan gelir (gerçekte yalnızca bilinen captcha sunucuları)."""
    from sonda.tarayici import sayfa
    sayfa.CAPTCHA_SUNUCULARI["localhost"] = "/captcha"
    yield
    sayfa.CAPTCHA_SUNUCULARI.pop("localhost", None)
