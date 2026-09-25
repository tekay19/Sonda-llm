"""Chrome kontrolü (Playwright, CDP). Sayfayı modele anlatılabilir numaralı öğe listesine çevirir ve eylemleri uygular.

Güvenlik kararları burada değil koruma.py'de verilir; bu modül sadece uygular. Açıklama fonksiyonu her
çağrıda sayfaya yeniden verilir (window'a konmaz): sayfa onu değiştirip öğeleri farklı gösteremesin.
"""
import os
import subprocess
import time
from pathlib import Path

import httpx
import trafilatura

KOK = Path(__file__).parent
YEDEK_PROFIL = KOK / "veri" / "chrome-profil"
YEDEK_PORT = 9223
CHROME = Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Google/Chrome/Application/chrome.exe"
ZAMAN_ASIMI = 20000

_ACIKLA = r"""(e) => {
  const form = e.form || e.closest('form');
  const yazi = s => (s || '').replace(/\s+/g, ' ').trim();
  const girdi = ['INPUT', 'TEXTAREA', 'SELECT'].includes(e.tagName);
  let metin = '';
  if (e.labels && e.labels.length) metin = e.labels[0].innerText;
  if (!metin && !girdi) metin = e.innerText;
  if (!metin && e.querySelector) { const img = e.querySelector('img[alt]'); if (img) metin = img.alt; }
  const r = e.getBoundingClientRect();
  const d = {
    no: Number(e.getAttribute('data-sonda-id')) || 0,
    etiket: e.tagName.toLowerCase(), rol: e.getAttribute('role') || '',
    tip: (e.getAttribute('type') || '').toLowerCase(), ad: e.getAttribute('name') || '', kimlik: e.id || '',
    otomatik: (e.getAttribute('autocomplete') || '').toLowerCase(), yer: e.getAttribute('placeholder') || '',
    aria: e.getAttribute('aria-label') || '', baslik: e.getAttribute('title') || '',
    metin: yazi(metin).slice(0, 120),
    deger: (girdi ? String(e.value || '') : '').slice(0, 80),
    href: e.tagName === 'A' ? (e.href || '') : '',
    form: form ? [...document.forms].indexOf(form) : -1,
    form_eylem: form ? (form.getAttribute('action') || '') : '',
    ekranda: r.bottom > 0 && r.top < innerHeight,
  };
  if (e.tagName === 'SELECT') { d.secenekler = [...e.options].slice(0, 25).map(o => yazi(o.text)); d.deger = yazi(e.selectedOptions[0]?.text); }
  if (e.type === 'checkbox' || e.type === 'radio') d.secili = e.checked;
  return d;
}"""

_BAK = "() => { const acikla = " + _ACIKLA + r""";
  const SECICI = 'a[href], button, input:not([type=hidden]), select, textarea, summary, [role=button], [role=link], [role=tab], [role=checkbox], [role=radio], [role=option], [role=menuitem], [role=searchbox], [role=combobox], [contenteditable=""], [contenteditable=true], [onclick]';
  document.querySelectorAll('[data-sonda-id]').forEach(e => e.removeAttribute('data-sonda-id'));
  const gorunur = e => { const r = e.getBoundingClientRect(); if (r.width < 2 || r.height < 2) return false;
    const s = getComputedStyle(e); return s.visibility !== 'hidden' && s.display !== 'none' && Number(s.opacity) > 0.05; };
  const ogeler = []; let no = 0;
  for (const e of document.querySelectorAll(SECICI)) {
    if (e.disabled || !gorunur(e)) continue;
    e.setAttribute('data-sonda-id', ++no);
    ogeler.push(acikla(e));
  }
  const metin = document.body ? document.body.innerText.replace(/\n{3,}/g, '\n\n') : '';
  return { url: location.href, baslik: document.title, ogeler, metin: metin.slice(0, 2500) };
}"""

_BILGI = "(no) => { const acikla = " + _ACIKLA + r""";
  const e = document.querySelector(`[data-sonda-id="${no}"]`);
  if (!e) return null;
  const form = e.form || e.closest('form');
  const kardes = form ? [...form.querySelectorAll('input:not([type=hidden]), select, textarea')].map(acikla) : [];
  return { oge: acikla(e), form_ogeleri: kardes };
}"""


class BaglantiHatasi(Exception):
    pass


class Tarayici:
    def __init__(self, sayfa, kapat=None):
        self._kapat = kapat
        self._ac(sayfa)

    def _ac(self, sayfa):
        self.sayfa = sayfa
        sayfa.on("popup", self._acilir_pencere)
        sayfa.on("dialog", lambda d: d.dismiss())  # confirm("Sipariş verilsin mi?") gibi pencereler reddedilir

    def _acilir_pencere(self, yeni):
        self._ac(yeni)  # window.open ile açılan sekmede çalışmaya devam et

    @property
    def url(self):
        return self.sayfa.url

    @property
    def baslik(self):
        try:
            return self.sayfa.title()
        except Exception:
            return ""

    def _bekle(self):
        try:
            self.sayfa.wait_for_load_state("domcontentloaded", timeout=ZAMAN_ASIMI)
        except Exception:
            pass
        self.sayfa.wait_for_timeout(700)  # JS ile çizilen içerik için kısa pay

    def _loc(self, no):
        return self.sayfa.locator(f'[data-sonda-id="{int(no)}"]').first

    def bak(self):
        return self.sayfa.evaluate(_BAK)

    def oge_bilgisi(self, no):
        return self.sayfa.evaluate(_BILGI, int(no))

    def git(self, url):
        self.sayfa.goto(url, wait_until="domcontentloaded", timeout=ZAMAN_ASIMI)
        self._bekle()

    def tikla(self, no):
        loc = self._loc(no)
        loc.evaluate("e => { const a = e.closest('a'); if (a && a.target) a.removeAttribute('target'); }")
        loc.click(timeout=5000)
        self._bekle()

    def yaz(self, no, metin, enter=False):
        loc = self._loc(no)
        loc.fill(str(metin), timeout=5000)
        if enter:
            loc.press("Enter")
            self._bekle()

    def sec(self, no, deger):
        loc = self._loc(no)
        try:
            loc.select_option(label=str(deger), timeout=5000)
        except Exception:
            loc.select_option(value=str(deger), timeout=5000)
        self._bekle()

    def kaydir(self, yon="asagi"):
        self.sayfa.mouse.wheel(0, -700 if yon == "yukari" else 700)
        self.sayfa.wait_for_timeout(500)

    def geri(self):
        self.sayfa.go_back(wait_until="domcontentloaded", timeout=ZAMAN_ASIMI)
        self._bekle()

    def vurgula(self, no):
        try:
            self.sayfa.bring_to_front()
            self._loc(no).evaluate("e => { e.style.outline = '4px solid #e5484d'; e.style.outlineOffset = '3px';"
                                   " e.scrollIntoView({ block: 'center' }); }", timeout=3000)
        except Exception:
            pass

    def ekran_goruntusu(self):
        return self.sayfa.screenshot(type="jpeg", quality=60)

    def tam_metin(self):
        metin = trafilatura.extract(self.sayfa.content(), include_tables=True) or ""
        return metin or self.sayfa.evaluate("() => document.body ? document.body.innerText : ''")

    def kapat(self):
        if self._kapat:
            self._kapat()


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
