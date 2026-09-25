"""Sonda'nın giriş noktası: moda göre araştırma ya da tarayıcı görevi çalıştırır ve arayüze olay akışı üretir.
  adim     -> araştırma/görev adımı
  kaynak   -> numaralı kaynak
  token    -> cevap metni parçası
  sifirla  -> o ana kadar yazılan taslağı temizle (model araca döndü)
  oneriler -> takip soruları
  bitti / hata
Görev modu olayları (gorev_basladi, kullaniciya, devam_edildi, nabiz) sonda/gorev'de tanımlıdır."""
import re
import threading
import time

from . import gorev, hafiza, koruma
from .arastirma import derin, hizli, sohbet
from .arastirma.promptlar import HAFIZA_PROMPTU, ONERI_PROMPTU
from .model import ModelHatasi
from .ortak import json_sor
from .yonlendirme import yon_belirle


# Birinci şahıs ifadeleri: hafıza çıkarımı sadece bunlar varsa çalışır (gereksiz model çağrısını önler)
_KISISEL = re.compile(r"\b(ben|benim|bana|beni|bende|adım|ismim|hatırla|unutma|bizim|eşim|oğlum|kızım)\b|"
                      r"\w+(ıyorum|iyorum|uyorum|üyorum|yorum|dım|dim|dum|düm|tım|tim|tum|tüm|ım|im|um|üm)\b",
                      re.IGNORECASE)


def sifresiz(metin, gizliler=()):
    """Mesajda verilen şifre yönlendirme, başlık ve sohbet modellerine gitmesin (görev kendi yer tutucusunu kullanır).
    gizliler: başka mesajlarda verilmiş şifreler (şifre sözcüğü olmadan tekrarlanabilir)."""
    return koruma.gizle(metin, koruma.gizli_adaylar(metin) | set(gizliler))


def oneriler(model, soru, cevap):
    if len(cevap) < 80:
        return
    try:
        veri = json_sor(model, ONERI_PROMPTU.format(soru=soru, cevap=cevap[:3000]))
    except ModelHatasi:
        return  # cevap zaten verildi; öneri eksikliği hata sayılmaz
    oneriler = [o for o in veri.get("oneriler", []) if isinstance(o, str) and o.strip()][:3]
    if oneriler:
        yield {"tur": "oneriler", "liste": oneriler}


def hafizayi_guncelle(model, mesaj):
    """Arka planda çalışır: kullanıcının mesajından kalıcı bilgi çıkarıp hafızaya ekler."""
    if not _KISISEL.search(mesaj):
        return
    try:
        bilinen = "\n".join(f"- {b['metin']}" for b in hafiza.yukle()) or "(yok)"
        veri = json_sor(model, HAFIZA_PROMPTU.format(bilinen=bilinen, mesaj=mesaj[:2000]))
        bilgiler = [b for b in veri.get("bilgiler", []) if isinstance(b, str) and 5 < len(b) < 200][:5]
        if bilgiler:
            hafiza.ekle(bilgiler)
    except Exception:
        pass


def baslik_uret(model, soru):
    veri = json_sor(model, 'Kullanıcının ilk mesajı için 2-5 kelimelik Türkçe bir sohbet başlığı yaz. '
                            'Sadece JSON: {"baslik": "..."}', soru)
    baslik = str(veri.get("baslik", "")).strip().strip('"')
    return baslik[:60] or soru[:60]


def calistir(soru, gecmis, model, mod, onceki_kaynaklar=(), diger_sohbetler=(), oneri=True):
    basla = time.time()
    cevap = ""
    gizliler = set().union(koruma.gizli_adaylar(soru), *(koruma.gizli_adaylar(m["content"]) for m in gecmis),
                           *(koruma.gizli_adaylar(b) for b in diger_sohbetler))
    temiz_soru = sifresiz(soru, gizliler)
    temiz_gecmis = [{**m, "content": sifresiz(m["content"], gizliler)} for m in gecmis]
    diger_sohbetler = [sifresiz(b, gizliler) for b in diger_sohbetler]  # başlık ilk mesajdan kesilmiş olabilir
    try:
        if mod == "gorev":
            # Görev modunda her mesaj tarayıcı açmasın: sohbet ve kısa bilgi soruları doğrudan cevaplanır
            hedef = yon_belirle(model, temiz_soru, temiz_gecmis)
            yield {"tur": "yon", "hedef": hedef}
            oneri = False
            if hedef == "gorev":
                uretec = gorev.calistir(soru, model, gecmis)  # görev şifreyi yer tutucuyla kendisi korur
            elif hedef == "sohbet":
                uretec = sohbet(temiz_soru, temiz_gecmis, model, onceki_kaynaklar, diger_sohbetler)
            else:
                uretec = hizli(temiz_soru, temiz_gecmis, model, onceki_kaynaklar, diger_sohbetler)
        else:
            uretec = (derin if mod == "derin" else hizli)(temiz_soru, temiz_gecmis, model, onceki_kaynaklar,
                                                          diger_sohbetler)
        for olay in uretec:
            if olay["tur"] == "cevap_bitti":
                cevap = olay["metin"]
                continue
            yield olay
        yield {"tur": "bitti", "sure": round(time.time() - basla, 1)}
        if oneri:
            yield from oneriler(model, temiz_soru, cevap)
    except ModelHatasi as e:
        yield {"tur": "hata", "metin": str(e), "bulut": True}
    except Exception as e:
        yield {"tur": "hata", "metin": f"{type(e).__name__}: {e}"}
    finally:
        if mod != "gorev":  # görev mesajında şifre olabilir: hafızaya yazılmasın
            threading.Thread(target=hafizayi_guncelle, args=(model, temiz_soru), daemon=True).start()
