"""Görevlerin yönetimi: kalıcı tarayıcı iş parçacığı, devam/durdur komutları, olay akışı.

Playwright'ın senkron API'si onu başlatan iş parçacığına bağlıdır; FastAPI ise akışın her adımını farklı bir
iş parçacığında çalıştırabilir. Ayrıca Chrome her yeni bağlantıda izin ister, bağlantı saklanmalıdır.
Bu yüzden bütün görevler tek ve kalıcı bir tarayıcı iş parçacığında (_ISCI) sırayla yürür; olaylar kuyrukla taşınır."""
import queue
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from .. import tarayici
from . import ayar, dongu


def _dene(kontrol):
    """Otomatik devam kontrolü. Sayfa yönlenirken okuma geçici hata verebilir: bu "henüz değil" sayılır.
    Sekme kapandıysa görev bitmeli, o yüzden SekmeKapandi yükselir."""
    try:
        return kontrol()
    except tarayici.SekmeKapandi:
        raise
    except Exception:
        return False


class Gorev:
    """Bir görevin arayüzden gelen komutları."""

    def __init__(self):
        self.id = uuid.uuid4().hex[:12]
        self.durdu = threading.Event()
        self.koptu = False
        self._komutlar = queue.Queue()

    def komut(self, ad):
        if ad == "durdur":
            self.durdu.set()
        self._komutlar.put(ad)

    def bekle(self, otomatik=None):
        """Kullanıcının komutunu bekler. otomatik verilirse aralıklarla çağrılır; True dönerse "otomatik" döner."""
        son = time.monotonic() + ayar.BEKLEME_SURESI
        while (kalan := son - time.monotonic()) > 0:
            try:
                ad = self._komutlar.get(timeout=min(kalan, ayar.IKI_ADIM_KONTROL) if otomatik else kalan)
            except queue.Empty:
                if otomatik and _dene(otomatik):
                    return "otomatik"
                continue
            if ad in ("devam", "durdur"):
                return ad
        return "zaman_asimi"

    def temizle(self):
        while not self._komutlar.empty():
            self._komutlar.get_nowait()


GOREVLER: dict[str, Gorev] = {}


_ISCI = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sonda-tarayici")


def tarayici_isinde(fn, *arg):
    """fn'i tarayıcı iş parçacığında çalıştırıp sonucunu döner (Playwright nesnelerine dışarıdan erişim için)."""
    return _ISCI.submit(fn, *arg).result()


def komut_ver(gorev_id, komut):
    g = GOREVLER.get(gorev_id)
    if not g or komut not in ("devam", "durdur"):
        return False
    g.komut(komut)
    return True


def calistir(gorev_metni, model, gecmis=(), tarayici_ac=None):
    onceki_suruyor = bool(GOREVLER)
    g = Gorev()
    GOREVLER[g.id] = g
    onceki = "\n".join(f"{m['role']}: {m['content'][:500]}" for m in list(gecmis)[-4:])
    kuyruk, son = queue.Queue(), object()

    def isci():
        try:
            for olay in dongu.yurut(g, gorev_metni, onceki, model, tarayici_ac or tarayici.baglan):
                kuyruk.put(olay)
        except Exception as h:
            kuyruk.put({"tur": "hata", "metin": f"{type(h).__name__}: {h}"})
        finally:
            kuyruk.put(son)

    _ISCI.submit(isci)
    try:
        yield {"tur": "gorev_basladi", "id": g.id}
        if onceki_suruyor:  # tek tarayıcı işçisi: yeni görev sıraya girer, kullanıcı bunu bilsin
            yield {"tur": "anlatim", "metin": "Önceki görev hâlâ sürüyor; o bitince bu göreve başlayacağım."}
        while True:
            try:
                olay = kuyruk.get(timeout=ayar.NABIZ_ARALIGI)
            except queue.Empty:
                yield {"tur": "nabiz"}
                continue
            if olay is son:
                break
            yield olay
    finally:
        g.koptu = True   # normal bitişte de zararsız: işçi zaten bitti
        g.komut("durdur")
        GOREVLER.pop(g.id, None)
