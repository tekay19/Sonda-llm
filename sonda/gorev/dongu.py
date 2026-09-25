"""Görev döngüsü: bak -> karar -> koruma -> uygula; kullanıcıya devretme, 2FA bekleme, sonuç yazma."""
import json
import time

import ollama

from .. import koruma, tarayici
from ..arastirma.kaynaklar import Kaynaklar
from ..ortak import SECENEKLER, bugun
from ..web import alan_adi
from . import ayar
from . import karar as kararlar
from .eylemler import adim, uygula
from .istem import istem
from .kayit import GorevKaydi
from .promptlar import CAPTCHA_SEBEBI, DEVAM_METNI, IKI_ADIM_SEBEBI, IKI_ADIM_TAMAM, SONUC_PROMPTU
from .sayfa import SayfaHafizasi, eksik_form_alanlari, iki_adim_mi


class GizliListe(list):
    """Adım geçmişi: eklenen her satırda şifreler gizlenir (model üretimi metinler de dahil)."""

    def __init__(self, gizliler):
        super().__init__()
        self.gizliler = gizliler

    def append(self, metin):
        super().append(koruma.gizle(metin, self.gizliler))


_ZOR_DURUM = ("Eylem başarısız", "Henüz bitirme", "Önce", "🔒", "Geçersiz", "Yalnızca")


def dusunmeli(derinlik, adim_no, geri_bildirim):
    """Düşünme modu pahalıdır: bir şey ters gittiğinde ve derin görevlerde düzenli aralıklarla açılır."""
    if geri_bildirim.startswith(_ZOR_DURUM) or "öğe yok" in geri_bildirim or "Dikkat:" in geri_bildirim:
        return True
    return bool(ayar.DUSUNME_ARALIGI) and derinlik["derinlik"] == "derin" and adim_no % ayar.DUSUNME_ARALIGI == 1


def devret(g, sebep, otomatik=None, gizliler=()):
    g.temizle()
    for gizli in gizliler:  # modelin yazdığı sebepte şifre geçebilir
        if len(gizli) >= 4:
            sebep = sebep.replace(gizli, "•••")
    yield {"tur": "kullaniciya", "id": g.id, "sebep": sebep}
    komut = "durdur" if g.durdu.is_set() else g.bekle(otomatik)
    yield {"tur": "devam_edildi", "komut": komut}
    return komut


def bak(t, ekran_iste):
    """(sayfa, ekran görüntüsü ya da None) döner. Sekme kapandıysa SekmeKapandi yükselir."""
    try:
        sayfa = t.bak()
    except tarayici.SekmeKapandi:
        raise
    except Exception as h:
        sayfa = {"url": t.url, "baslik": "", "ogeler": [], "metin": f"(sayfa okunamadı: {h})"}
    ekran = None
    if ekran_iste or len(sayfa["ogeler"]) < 5:
        try:
            ekran = t.ekran_goruntusu()
        except tarayici.SekmeKapandi:
            raise
        except Exception:
            pass
    return sayfa, ekran


def dongu(g, gorev_metni, onceki, model, t, durum, derinlik):
    """Olay üretir; sonucu durum sözlüğüne yazar (notlar, adimlar, hafiza, sonuc, hal)."""
    notlar, adimlar, hafiza_ = durum["notlar"], durum["adimlar"], durum["hafiza"]
    maks = min(ayar.MAKS_ADIM, derinlik["maks_adim"])
    geri_bildirim, ekran_iste, son_imza, tekrar, bitir_red = "", False, None, 0, 0
    yapilan, erken_red, form_red, son_mesaj = 0, False, False, ""
    captcha_denenen, son_okuma, son_imzalar = set(), None, []
    durum["gizli"].update(koruma.gizli_adaylar(gorev_metni))
    kayit = GorevKaydi(g.id, durum["gizli"])
    def ilerleme():  # not sayısı ve açılan gerçek sayfa sayısı
        return len(notlar), sum(1 for u in hafiza_.sayfalar if u != "about:blank")

    adim_no, uzatildi, izler = 0, False, {}  # izler: adım -> o adımdan önceki ilerleme
    while True:
        if adim_no >= maks:
            # Uzun görevler kısa kesilmesin: son adımlarda yeni not ya da sayfa varsa bir kez yarısı kadar uzat
            pencere = max(1, min(ayar.ILERLEME_PENCERESI, maks // 2))
            if uzatildi or ilerleme() <= izler.get(adim_no - pencere, ilerleme()):
                break
            uzatildi, maks = True, maks + max(1, maks // 2)
            yield {"tur": "anlatim", "metin": "Görev beklediğimden uzun sürüyor ama ilerliyor; devam ediyorum."}
        izler[adim_no] = ilerleme()
        adim_no += 1
        if (derinlik["derinlik"] in ("orta", "derin") and adim_no > 1
                and (adim_no - 1) % ayar.DEGERLENDIRME_ARALIGI == 0):
            ara = kararlar.ilerleme_degerlendir(model, gorev_metni, derinlik, notlar, hafiza_)
            if ara.get("plan"):
                derinlik["plan"] = ara["plan"]
            if ara.get("degerlendirme"):
                metin = ara["degerlendirme"]
                for gizli in koruma.gizli_adaylar(gorev_metni) | durum["gizli"]:
                    metin = metin.replace(gizli, "•••")
                yield {"tur": "anlatim", "metin": metin}
                adimlar.append(f"{adim_no}. ara değerlendirme: {metin[:150]}")
        if g.durdu.is_set():
            durum["kod"], durum["hal"] = "durduruldu", "Kullanıcı görevi durdurdu."
            return
        sayfa, ekran = bak(t, ekran_iste)
        if iki_adim_mi(sayfa):
            yield adim("engel", "İki adımlı doğrulama bekleniyor")
            adimlar.append(f"{adim_no}. iki adımlı doğrulama (2FA) kullanıcıya bırakıldı")
            komut = yield from devret(g, IKI_ADIM_SEBEBI, otomatik=lambda: not iki_adim_mi(t.bak()), gizliler=durum["gizli"])
            if komut not in ("devam", "otomatik"):
                durum["hal"] = ("Kullanıcı görevi durdurdu." if komut == "durdur"
                                else "Kullanıcı 15 dakika içinde doğrulamayı yapmadığı için görev bitti.")
                durum["kod"] = "durduruldu" if komut == "durdur" else "zaman_asimi"
                return
            geri_bildirim, son_imza, tekrar = IKI_ADIM_TAMAM, None, 0
            sayfa, ekran = bak(t, ekran_iste)
        if sayfa.get("captcha") and t.url not in captcha_denenen:
            # Kullanıcı izni: robot doğrulamasının onay kutusu modele sorulmadan işaretlenir; yetmezse kullanıcıya
            captcha_denenen.add(t.url)
            onaylandi = t.captcha_onayla()
            yield adim("tikla", "Robot doğrulamasının onay kutusu işaretlendi" if onaylandi else "Robot doğrulaması bekleniyor")
            t.sayfa.wait_for_timeout(int(ayar.CAPTCHA_BEKLE * 1000))
            sayfa, ekran = bak(t, ekran_iste)
            geri_bildirim = "Robot doğrulaması geçildi; kaldığın yerden devam et."
            if sayfa.get("captcha"):
                adimlar.append(f"{adim_no}. robot doğrulaması kullanıcıya bırakıldı")
                komut = yield from devret(g, CAPTCHA_SEBEBI, otomatik=lambda: not t.bak().get("captcha"), gizliler=durum["gizli"])
                if komut not in ("devam", "otomatik"):
                    durum["hal"] = ("Kullanıcı görevi durdurdu." if komut == "durdur"
                                    else "Robot doğrulaması 15 dakika içinde yapılmadığı için görev bitti.")
                    durum["kod"] = "durduruldu" if komut == "durdur" else "zaman_asimi"
                    return
                geri_bildirim = "Robot doğrulaması tamamlandı; kaldığın yerden devam et."
                sayfa, ekran = bak(t, ekran_iste)
        hafiza_.goruldu(sayfa)
        ekran_iste = False
        istem_metni = istem(gorev_metni, onceki, derinlik, notlar, hafiza_, adimlar, sayfa, geri_bildirim, adim_no, maks)
        dusun = dusunmeli(derinlik, adim_no, geri_bildirim)
        karar = kararlar.karar_al(model, istem_metni, ekran, dusun)
        kayit.yaz({"adim": adim_no, "zaman": time.strftime("%H:%M:%S"), "url": sayfa["url"], "dusun": dusun,
                   "ekran": ekran is not None, "istem": istem_metni, "karar": karar})
        if g.durdu.is_set():  # model düşünürken Durdur'a basıldı: gelen eylem uygulanmaz
            durum["kod"], durum["hal"] = "durduruldu", "Kullanıcı görevi durdurdu."
            return
        if karar is None:
            geri_bildirim = "Geçersiz cevap verdin; listedeki eylemlerden birini geçerli JSON olarak döndür."
            adimlar.append(f"{adim_no}. (geçersiz cevap)")
            continue
        e = karar["eylem"]
        mesaj = str(karar.get("mesaj") or "").strip()[:300]
        for gizli in koruma.gizli_adaylar(gorev_metni) | durum["gizli"]:
            mesaj = mesaj.replace(gizli, "•••")
        if mesaj and mesaj != son_mesaj:
            yield {"tur": "anlatim", "metin": mesaj}
            son_mesaj = mesaj
        dusunce = koruma.gizle(str(karar.get("dusunce") or "").strip()[:200], durum["gizli"])
        dusunce_ek = f" — düşünce: {dusunce}" if dusunce else ""
        if e in ("bitir", "sana_birak") and not form_red and (eksik_alan := eksik_form_alanlari(sayfa["ogeler"], gorev_metni)):
            form_red = True
            geri_bildirim = ("Önce görevde istenen şu alanları doldur/işaretle; hâlâ boş ya da işaretsizler: "
                             + ", ".join(f"“{a}”" for a in eksik_alan) + ". Yapmadığın bir şeyi yapılmış sayma.")
            adimlar.append(f"{adim_no}. {e} istedi ama istenen form alanları eksikti{dusunce_ek}")
            continue
        if e == "bitir":
            siteler = sorted({alan_adi(n["url"]) for n in notlar})
            if len(siteler) < derinlik["min_site"] and bitir_red < ayar.BITIR_RED_SINIRI and adim_no < maks - 3:
                bitir_red += 1
                geri_bildirim = (f"Henüz bitirme: bu görev için en az {derinlik['min_site']} farklı siteden bilgi "
                                 f"toplamalısın; şu an {len(siteler)} siteden notun var"
                                 + (f" ({', '.join(siteler)})" if siteler else "")
                                 + ". Başka kaynaklara da bak (gerekirse İngilizce arama yap), bulduklarını not al.")
                adimlar.append(f"{adim_no}. bitirmek istedi, kaynak yetersiz olduğu için devam{dusunce_ek}")
                continue
            eksikler = hafiza_.eksik_notlu()
            if derinlik.get("inceleme"):
                eksikler += [x for x in hafiza_.eksik_ziyaret() if x not in eksikler]
            if eksikler and bitir_red < ayar.BITIR_RED_SINIRI and adim_no < maks - 3:
                bitir_red += 1
                geri_bildirim = ("Henüz bitirme: not aldığın bazı sayfaları tam incelemedin: "
                                 + "; ".join(f"{u} ({n})" for u, n in eksikler[:3])
                                 + ". Bu sayfalara dönüp kaydır ve 'daha fazla' butonlarını aç; daha iyi seçenek "
                                   "olabilir. Notlarını gerekirse düzelt.")
                adimlar.append(f"{adim_no}. bitirmek istedi, sayfalar tam incelenmediği için devam{dusunce_ek}")
                continue
            durum["sonuc"], durum["hal"] = koruma.gizle(karar.get("sonuc", ""), durum["gizli"]), "Görev tamamlandı."
            durum["kod"] = "tamamlandi"
            return

        imza = (f"{e}:{karar.get('no')}" if e in ("yaz", "sec") else  # aynı alana farklı metin de tekrardır
                json.dumps({k: v for k, v in karar.items() if k not in ("dusunce", "mesaj")}, sort_keys=True, ensure_ascii=False))
        tekrar = tekrar + 1 if imza == son_imza and e != "kaydir" else 1
        son_imza = imza
        son_imzalar = (son_imzalar + [imza])[-6:]
        # iki eylem arasında gidip gelmek de takılmadır (ör. "Edit overview" <-> yaz)
        salinim = len(son_imzalar) == 6 and len(set(son_imzalar)) == 2 and             all(x != y for x, y in zip(son_imzalar, son_imzalar[1:]))  # A-B-A-B-A-B
        if tekrar == ayar.TAKILMA_EKRAN:
            ekran_iste = True

        sebep, no = None, karar.get("no")
        if e == "sana_birak" and not yapilan and t.url in ("", "about:blank") and not erken_red:
            erken_red = True
            geri_bildirim = ("Önce görevdeki sayfaya git ve izinli olan kısmı yap (ör. sayfayı aç, e-posta gibi alanları "
                             "doldur); sadece gerçekten senin yapamayacağın adımı kullanıcıya bırak.")
            adimlar.append(f"{adim_no}. hiçbir şey yapmadan devretmek istedi, önce denemesi istendi")
            continue
        if e == "sana_birak":
            sebep = str(karar["sebep"])
        elif tekrar >= ayar.TAKILMA_DEVRET or salinim:
            sebep = "Aynı adımı tekrar tekrar deniyorum, takıldım. Sayfaya bakıp yardım eder misin?"
        oge = None
        if not sebep and e in ("tikla", "yaz", "sec"):
            bilgi = t.oge_bilgisi(no)
            if bilgi is None:
                geri_bildirim = f"[{no}] numaralı öğe yok; sayfa değişmiş olabilir. Güncel listeden seç."
                adimlar.append(f"{adim_no}. {e} [{no}] -> öğe yok")
                continue
            oge = bilgi["oge"]
            k = koruma.kontrol(karar, oge, bilgi["form_ogeleri"], gorev_metni=gorev_metni, url=t.url,
                               gizliler=durum["gizli"])
            if not k.izin:
                t.vurgula(no)
                yield adim("engel", k.sebep)
                adimlar.append(f"{adim_no}. {e} “{koruma.oge_adi(oge)}” -> ENGELLENDİ, kullanıcıya bırakıldı")
                hafiza_.eylem(t.url, f"“{koruma.oge_adi(oge)}” kullanıcıya bırakıldı")
                sebep = k.sebep
            karar["enter_izni"] = k.enter
        elif not sebep and e == "git":
            k = koruma.kontrol(karar, gorev_metni=gorev_metni, gizliler=durum["gizli"])
            if not k.izin:
                geri_bildirim = k.sebep
                adimlar.append(f"{adim_no}. git {karar['url'][:80]} -> engellendi")
                continue

        if sebep:
            if e == "sana_birak" or tekrar >= ayar.TAKILMA_DEVRET or salinim:
                adimlar.append(f"{adim_no}. kullanıcıya bırakıldı: {sebep[:100]}")
            komut = yield from devret(g, sebep, gizliler=durum["gizli"])
            if komut != "devam":
                durum["hal"] = ("Kullanıcı görevi durdurdu." if komut == "durdur"
                                else "Kullanıcı 15 dakika yanıt vermediği için görev bitti.")
                durum["kod"] = "durduruldu" if komut == "durdur" else "zaman_asimi"
                return
            geri_bildirim, son_imza, tekrar, son_imzalar = DEVAM_METNI, None, 0, []
            continue

        if e == "captcha":
            onaylandi = t.captcha_onayla()
            yield adim("tikla", "Robot doğrulamasının onay kutusu işaretlendi" if onaylandi else "Robot doğrulaması bulunamadı")
            adimlar.append(f"{adim_no}. captcha -> {'onay kutusu işaretlendi' if onaylandi else 'bulunamadı'}")
            geri_bildirim = "Onay kutusu işaretlendi." if onaylandi else "Sayfada işaretlenecek robot doğrulaması bulunamadı."
            if onaylandi:
                t.sayfa.wait_for_timeout(int(ayar.CAPTCHA_BEKLE * 1000))
                if t.bak().get("captcha"):  # resimli bulmaca: kullanıcı çözer, bitince otomatik devam
                    komut = yield from devret(g, CAPTCHA_SEBEBI, otomatik=lambda: not t.bak().get("captcha"), gizliler=durum["gizli"])
                    if komut not in ("devam", "otomatik"):
                        durum["hal"] = ("Kullanıcı görevi durdurdu." if komut == "durdur"
                                        else "Robot doğrulaması 15 dakika içinde çözülmediği için görev bitti.")
                        durum["kod"] = "durduruldu" if komut == "durdur" else "zaman_asimi"
                        return
                    geri_bildirim = "Robot doğrulaması tamamlandı; kaldığın yerden devam et."
            yapilan += 1
            continue
        if e == "oku":
            okuma = (t.url, (sayfa.get("kaydirma") or {}).get("y"))
            if okuma == son_okuma:  # arada sayfa değişmedi: aynı içeriği yeniden okumak dakikalar kaybettirir
                geri_bildirim = ("Bu sayfayı aynı konumda zaten okudun; içeriği hafızanda. Başka bir adım seç: "
                                 "kaydır, 'more' aç, not al ya da ilerle.")
                adimlar.append(f"{adim_no}. oku -> aynı sayfa zaten okunmuştu")
                continue
            son_okuma = okuma
        onceki_url = t.url
        if e == "not_al":  # şifre notlara ve oradan cevaba sızmasın
            for gizli in koruma.gizli_adaylar(gorev_metni) | durum["gizli"]:
                karar["metin"] = str(karar["metin"]).replace(gizli, "•••")
        if e in ("yaz", "sec") and koruma.hassas_alan(oge):
            karar["gizli"] = True  # görevde verilen şifre: hiçbir çıktıda açık yazılmaz
            durum["gizli"].add(str(karar.get("metin") or karar.get("deger")))
        try:
            olay, geri_bildirim = uygula(t, karar, gorev_metni, notlar, oge)
        except tarayici.SekmeKapandi:
            raise
        except Exception as h:
            geri_bildirim = f"Eylem başarısız: {type(h).__name__}: {str(h).splitlines()[0][:200]}"
            yield adim("hata", geri_bildirim)
            adimlar.append(f"{adim_no}. {e} -> başarısız{dusunce_ek}")
            continue
        yield olay
        yapilan += 1
        ekran_iste = ekran_iste or e == "bak"
        adimlar.append(f"{adim_no}. {olay['metin'][:120]}{dusunce_ek}")
        if e == "not_al":
            hafiza_.not_(onceki_url, str(karar["metin"])[:200])
            if eksik := hafiza_.eksik(onceki_url):
                geri_bildirim += (f" Dikkat: {eksik}; not aldığın bilgi eksik olabilir (ör. daha ucuz ya da daha "
                                  "iyi seçenek aşağıda olabilir). Kaydırıp/açıp kontrol et, gerekirse notu düzelt.")
        elif e == "kaydir":
            hafiza_.eylem(onceki_url, "kaydırıldı")
        elif e != "git":
            hafiza_.eylem(onceki_url, olay["metin"][:80])
    durum["kod"], durum["hal"] = "adim_siniri", f"Adım sınırı ({maks}) doldu; görev yarım kalmış olabilir."


def sonuc_yaz(model, gorev_metni, durum):
    kaynaklar = Kaynaklar()
    satirlar = []
    for n in durum["notlar"]:
        no, olay = kaynaklar.ekle(n["url"], n["baslik"] or alan_adi(n["url"]))
        if olay:
            yield olay
        satirlar.append(f"[{no}] {n['metin']}")
    for gizli in durum.get("gizli", ()):
        gorev_metni = gorev_metni.replace(gizli, "•••")
    istem = SONUC_PROMPTU.format(tarih=bugun(), durum=durum["hal"], gorev=gorev_metni, sonuc=durum["sonuc"] or "(yok)",
                                 notlar="\n".join(satirlar) or "(not yok)", sayfalar=durum["hafiza"].metin(),
                                 icerik=durum["hafiza"].icerik(ayar.SONUC_ICERIK),
                                 adimlar="\n".join(durum["adimlar"][-15:]) or "(yok)")
    cevap = ""
    derinlik = durum.get("derinlik") or {}
    dusun = bool(derinlik.get("inceleme") or derinlik.get("derinlik") == "derin")  # analizde önce düşün
    for parca in ollama.chat(model=model, stream=True, think=dusun, options=SECENEKLER,
                             messages=[{"role": "user", "content": istem}]):
        if parca.message.content:
            cevap += parca.message.content
            yield {"tur": "token", "metin": parca.message.content}
    yield {"tur": "cevap_bitti", "metin": cevap}


def yurut(g, gorev_metni, onceki, model, tarayici_ac):
    # Önceki mesajlarda verilmiş şifreler de korunur ve istemlere/kayıtlara açık yazılmaz
    onceki_gizli = koruma.gizli_adaylar(onceki)
    onceki = koruma.gizle(onceki, onceki_gizli)
    yield adim("baglan", "Chrome'a bağlanılıyor")
    try:
        t = tarayici_ac()
    except tarayici.BaglantiHatasi as h:
        yield {"tur": "token", "metin": str(h)}
        yield {"tur": "cevap_bitti", "metin": str(h)}
        return
    derinlik = kararlar.derinlik_belirle(model, gorev_metni, onceki)
    yield {"tur": "adim", "tip": "plan", "detay": derinlik["plan"],
           "metin": f"{derinlik['derinlik'].capitalize()} görev: en az {derinlik['min_site']} site, "
                    f"en fazla {derinlik['maks_adim']} adım"}
    gizliler = set()
    durum = {"notlar": [], "adimlar": GizliListe(gizliler), "hafiza": SayfaHafizasi(), "sonuc": "", "hal": "", "gizli": gizliler,
             "derinlik": derinlik}
    durum["gizli"].update(onceki_gizli)
    try:
        yield from dongu(g, gorev_metni, onceki, model, t, durum, derinlik)
    except tarayici.SekmeKapandi:
        yield adim("hata", "Sonda'nın sekmesi kapatıldı, görev durdu")
        durum["kod"], durum["hal"] = "sekme_kapandi", "Sonda'nın sekmesi kapatıldığı için görev yarıda kaldı."
    finally:
        try:
            t.kapat()
        except Exception:
            pass
    if not g.koptu:
        yield {"tur": "gorev_bitti", "durum": durum.get("kod", "tamamlandi")}
        yield from sonuc_yaz(model, gorev_metni, durum)
