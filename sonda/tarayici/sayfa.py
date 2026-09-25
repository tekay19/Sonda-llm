"""Tek bir sekmenin kontrolü: bak, tıkla, yaz, kaydır... Güvenlik kararları koruma.py'dedir; burası uygular."""
from urllib.parse import urlparse

import trafilatura

from .js import BAK, CAPTCHA_BASLIKLARI, CAPTCHA_KUTULARI, ENGEL

# Bilinen robot doğrulaması sunucuları -> çerçeve adresinin yol öneki. Adresin herhangi bir yerinde geçen kelimeye
# değil, gerçek ana makineye bakılır (final inceleme: "evil.example/?hcaptcha.com" captcha sayılıyordu).
CAPTCHA_SUNUCULARI = {"challenges.cloudflare.com": "/", "hcaptcha.com": "/", "newassets.hcaptcha.com": "/",
                      "assets.hcaptcha.com": "/", "www.google.com": "/recaptcha/", "google.com": "/recaptcha/",
                      "www.recaptcha.net": "/recaptcha/", "recaptcha.net": "/recaptcha/"}


def captcha_adresi_mi(url):
    p = urlparse(url)
    onek = CAPTCHA_SUNUCULARI.get((p.hostname or "").lower())
    return onek is not None and p.path.startswith(onek)


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
        # .first yok: aynı numarayı taşıyan ikinci bir öğe (gölge DOM tuzağı) varsa Playwright işlemi reddeder
        return self.sayfa.locator(f'[data-sonda-id="{int(no)}"]')

    def bak(self):
        # evaluate zaman aşımı almaz: JS'i kilitlenen bir sayfa tek görev işçisini sonsuza dek bekletirdi.
        # wait_for_function zaman aşımı alır; aralıklı yoklama arka plan sekmesinde de çalışır (rAF durur).
        tutamac = self.sayfa.wait_for_function("() => (" + BAK + ")()", polling=100, timeout=ZAMAN_ASIMI)
        sayfa = tutamac.json_value()
        sayfa["captcha"] = bool(self._captcha_cerceveleri()) or \
            any(b in sayfa["baslik"].lower() for b in CAPTCHA_BASLIKLARI)
        return sayfa

    def _captcha_cerceveleri(self):
        """Görünür robot doğrulaması çerçeveleri ve ekrandaki kutuları (görünmez reCAPTCHA sayılmaz)."""
        ana, sonuc = self.sayfa.main_frame, []
        for f in self.sayfa.frames:
            if f is ana or not captcha_adresi_mi(f.url):
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
            x, y = alan["x"] + min(30, alan["width"] / 2), alan["y"] + alan["height"] / 2
            try:  # o noktada en üstte gerçekten bu çerçeve mi? (altındaki bir butona tıklatılmasın)
                ustte = cerceve.frame_element().evaluate("(f, n) => document.elementFromPoint(n[0], n[1]) === f", [x, y])
            except Exception:
                ustte = False
            if not ustte:
                continue
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
            self.sayfa.mouse.click(x, y)
            self._bekle()
            return True
        return False

    def oge_bilgisi(self, no):
        """Koruma kararı için öğe bilgisi. Playwright'ın izole dünyasından okunur: sayfa ana dünyada DOM'u
        (getAttribute, innerText...) değiştirse de koruma gerçeği görür. Numara birden fazla öğedeyse None."""
        loc = self._loc(no)
        try:
            if loc.count() != 1:
                return None
            oge, form = self._acikla(loc, int(no))
            kardesler = []
            if form is not None:
                alanlar = form.locator("input:not([type=hidden]), select, textarea")
                for i in range(min(alanlar.count(), 20)):
                    kardesler.append(self._acikla(alanlar.nth(i), 0)[0])
            return {"oge": oge, "form_ogeleri": kardesler}
        except SekmeKapandi:
            raise
        except Exception:
            return None

    def _acikla(self, loc, no):
        z = 3000

        def ozellik(ad):
            return loc.get_attribute(ad, timeout=z) or ""
        etiket = next((t for t in ("a", "button", "input", "select", "textarea", "summary")
                       if loc.locator(f"xpath=self::{t}").count()), "div")
        tip = ozellik("type").lower() if etiket in ("input", "button") else ""
        d = {"no": no, "etiket": etiket, "rol": ozellik("role"), "tip": tip, "ad": ozellik("name"),
             "kimlik": ozellik("id"), "otomatik": ozellik("autocomplete").lower(), "yer": ozellik("placeholder"),
             "aria": ozellik("aria-label"), "baslik": ozellik("title"), "href": ozellik("href") if etiket == "a" else "",
             "deger": "", "ekranda": True}
        metin = ""
        if etiket in ("input", "select", "textarea"):
            if d["kimlik"]:
                etiketler = self.sayfa.locator(f'label[for="{d["kimlik"].replace(chr(34), "")}"]')
                if etiketler.count():
                    metin = etiketler.first.inner_text(timeout=z)
            if not metin:
                ata = loc.locator("xpath=ancestor::label[1]")
                if ata.count():
                    metin = ata.inner_text(timeout=z)
            try:
                d["deger"] = loc.input_value(timeout=z)[:80]
            except Exception:
                pass
            if tip in ("checkbox", "radio"):
                d["secili"] = loc.is_checked(timeout=z)
        else:
            metin = loc.inner_text(timeout=z)
        d["metin"] = " ".join(metin.split())[:120]
        form = loc.locator("xpath=ancestor::form[1]")
        var = form.count() > 0
        d["form"] = 0 if var else -1
        d["form_eylem"] = (form.get_attribute("action", timeout=z) or "") if var else ""
        return d, (form if var else None)

    def git(self, url):
        self.sayfa.goto(url, wait_until="domcontentloaded", timeout=ZAMAN_ASIMI)
        self._bekle()

    def tikla(self, no):
        loc = self._loc(no)
        loc.evaluate("e => { const a = e.closest('a'); if (a && a.target) a.removeAttribute('target'); }")
        try:
            loc.click(timeout=4000, no_wait_after=True)
        except Exception:
            # Upwork'te görülen zaman aşımı: çoğunlukla üstte çerez bildirimi/pop-up vardır; modele nedenini söyle
            try:
                engel = loc.evaluate(ENGEL, timeout=3000)
            except Exception:
                engel = None
            if engel:
                raise TiklamaEngeli(f"Tıklanacak öğenin üstünde başka bir öğe var: “{engel}”. Önce onu kapat "
                                    "(ör. çerezleri kabul et / pop-up'ı kapat) ya da sayfayı kaydır.") from None
            # Kör yeniden tıklama yok: tıklama olmuş da olabilir, ya da öğe değişmiş olabilir (koruma yeniden bakmalı)
            try:
                loc.scroll_into_view_if_needed(timeout=2000)
            except Exception:
                pass
            raise RuntimeError("Tıklama zaman aşımına uğradı (tıklanmış da olabilir). Sayfanın yeni haline bak; "
                               "gerekirse öğeyi yeniden seçip tekrar dene.") from None
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
