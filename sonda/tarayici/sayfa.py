"""Tek bir sekmenin kontrolü: bak, tıkla, yaz, kaydır... Güvenlik kararları koruma.py'dedir; burası uygular."""
import trafilatura

from .js import BAK, BILGI, CAPTCHA_ADRESLERI, CAPTCHA_BASLIKLARI, CAPTCHA_KUTULARI, ENGEL


ZAMAN_ASIMI = 20000


class TiklamaEngeli(Exception):
    """Tıklanacak öğenin üstünde başka bir öğe (çerez bildirimi, pop-up) var."""


class SekmeKapandi(Exception):
    """Sonda'nın sekmesi (ve dönülecek önceki sekmeler) kapandı; büyük ihtimalle kullanıcı kapattı."""


class Tarayici:
    def __init__(self, sayfa, kapat=None):
        self._kapat = kapat
        self._onceki = []  # açılır pencereye geçince önceki sekmeler; pencere kapanırsa geri dönülür
        self._ac(sayfa)

    def _ac(self, sayfa):
        self._sayfa = sayfa
        sayfa.on("popup", self._acilir_pencere)
        sayfa.on("dialog", lambda d: d.dismiss())  # confirm("Sipariş verilsin mi?") gibi pencereler reddedilir

    def _acilir_pencere(self, yeni):
        self._onceki.append(self._sayfa)
        self._ac(yeni)  # window.open ile açılan sekmede çalışmaya devam et

    @property
    def sayfa(self):
        # Senkron Playwright olayları (açılır pencerenin kapanması gibi) ancak bir çağrı sırasında işler
        try:
            self._sayfa.wait_for_timeout(1)
        except Exception:
            pass
        while self._sayfa.is_closed() and self._onceki:
            self._sayfa = self._onceki.pop()
        if self._sayfa.is_closed():
            raise SekmeKapandi("Sonda'nın sekmesi kapatıldı.")
        return self._sayfa

    @property
    def url(self):
        try:
            return self.sayfa.url
        except SekmeKapandi:
            return self._sayfa.url  # son bilinen adres

    @property
    def baslik(self):
        try:
            return self.sayfa.title()
        except Exception:
            return ""

    def _bekle(self):
        try:
            self.sayfa.wait_for_load_state("domcontentloaded", timeout=ZAMAN_ASIMI)
        except SekmeKapandi:
            raise
        except Exception:
            pass
        try:
            self.sayfa.wait_for_timeout(700)  # JS ile çizilen içerik için kısa pay
        except SekmeKapandi:
            raise
        except Exception:
            pass  # açılır pencere bu arada kapandıysa sonraki erişimde önceki sekmeye dönülür

    def _loc(self, no):
        return self.sayfa.locator(f'[data-sonda-id="{int(no)}"]').first

    def bak(self):
        sayfa = self.sayfa.evaluate(BAK)
        sayfa["captcha"] = bool(self._captcha_cerceveleri()) or \
            any(b in sayfa["baslik"].lower() for b in CAPTCHA_BASLIKLARI)
        return sayfa

    def _captcha_cerceveleri(self):
        """Görünür robot doğrulaması çerçeveleri ve ekrandaki kutuları (görünmez reCAPTCHA sayılmaz)."""
        ana, sonuc = self.sayfa.main_frame, []
        for f in self.sayfa.frames:
            if f is ana or not any(a in f.url for a in CAPTCHA_ADRESLERI):
                continue
            try:
                kutu = f.frame_element().bounding_box()
            except Exception:
                continue
            if kutu and kutu["width"] > 20 and kutu["height"] > 20:
                sonuc.append((f, kutu))
        return sonuc

    def captcha_onayla(self):
        """Robot doğrulamasının onay kutusunu işaretler (kullanıcı izin verdi). Resimli bulmaca çözülmez."""
        for cerceve, alan in self._captcha_cerceveleri():
            for secici in CAPTCHA_KUTULARI:
                kutu = cerceve.locator(secici).first
                try:
                    if kutu.count() and kutu.is_visible():
                        kutu.click(timeout=5000)
                        self._bekle()
                        return True
                except Exception:
                    continue
            # Cloudflare: kutu kapalı shadow DOM'da, seçiciyle bulunamaz; insan gibi ekrandaki yerine (sol) tıkla
            self.sayfa.mouse.click(alan["x"] + min(30, alan["width"] / 2), alan["y"] + alan["height"] / 2)
            self._bekle()
            return True
        return False

    def oge_bilgisi(self, no):
        return self.sayfa.evaluate(BILGI, int(no))

    def git(self, url):
        self.sayfa.goto(url, wait_until="domcontentloaded", timeout=ZAMAN_ASIMI)
        self._bekle()

    def tikla(self, no):
        loc = self._loc(no)
        loc.evaluate("e => { const a = e.closest('a'); if (a && a.target) a.removeAttribute('target'); }")
        try:
            loc.click(timeout=4000)
        except Exception:
            # Upwork'te görülen zaman aşımı: çoğunlukla üstte çerez bildirimi/pop-up vardır; modele nedenini söyle
            try:
                engel = loc.evaluate(ENGEL, timeout=3000)
            except Exception:
                engel = None
            if engel:
                raise TiklamaEngeli(f"Tıklanacak öğenin üstünde başka bir öğe var: “{engel}”. Önce onu kapat "
                                    "(ör. çerezleri kabul et / pop-up'ı kapat) ya da sayfayı kaydır.") from None
            loc.scroll_into_view_if_needed(timeout=3000)
            loc.click(timeout=4000)
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
