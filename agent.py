"""Ajan orkestrasyonu. Her iki mod da arayüze olay (dict) akışı üretir:
  adim     -> araştırma adımı (tip: plan | ara | oku | dusun | hesap | yaz)
  kaynak   -> numaralı kaynak
  token    -> cevap metni parçası
  sifirla  -> o ana kadar yazılan taslağı temizle (model araca döndü)
  oneriler -> takip soruları
  bitti / hata
Görev modu olayları (gorev_basladi, kullaniciya, devam_edildi) gorev.py'de tanımlıdır.
"""
import json
import re
import threading
import time
from datetime import date

import ollama

import hafiza
from hesap import hesapla, tarih_hesapla
from webtools import alan_adi, sayfalari_oku, web_ara

AYLAR = "Ocak Şubat Mart Nisan Mayıs Haziran Temmuz Ağustos Eylül Ekim Kasım Aralık".split()
GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
MAKS_ARAC_TURU = 10
# Tüm çağrılarda aynı bağlam boyutu: değişirse Ollama modeli baştan yükler
SECENEKLER = {"num_ctx": 32768, "temperature": 0.3}
JSON_SECENEKLERI = {**SECENEKLER, "temperature": 0}


def bugun():
    g = date.today()
    return f"{g.day} {AYLAR[g.month - 1]} {g.year} {GUNLER[g.weekday()]}"


ARACLAR = [
    {"type": "function", "function": {
        "name": "web_ara",
        "description": "İnternette DuckDuckGo, Bing ve Brave üzerinde aynı anda arar; birleştirilmiş, "
                       "sıralanmış sonuçları (başlık, adres, özet) döner. Güncel olaylar için haber=true kullan.",
        "parameters": {"type": "object", "required": ["sorgular"], "properties": {
            "sorgular": {"type": "array", "items": {"type": "string"},
                         "description": "1-3 kısa sorgu. Kapsamı artırmak için Türkçe ve İngilizce varyant ekle."},
            "haber": {"type": "boolean", "description": "Son haberlerde ara"},
        }}}},
    {"type": "function", "function": {
        "name": "sayfa_oku",
        "description": "Verilen adreslerdeki sayfaları (HTML veya PDF) paralel okur ve soruyla en alakalı "
                       "bölümleri döner. Özetler yetersizse veya ayrıntı gerekiyorsa kullan.",
        "parameters": {"type": "object", "required": ["urller"], "properties": {
            "urller": {"type": "array", "items": {"type": "string"},
                       "description": "En fazla 6 adres; farklı sitelerden seç"},
        }}}},
    {"type": "function", "function": {
        "name": "hesapla",
        "description": "Matematiksel ifadeyi kesin olarak hesaplar (Python sözdizimi: + - * / ** %, sqrt, log, "
                       "round, factorial, comb, min, max, pi). Her türlü aritmetik, yüzde, faiz, birim çevirme "
                       "hesabında kafadan hesaplamak yerine BUNU kullan.",
        "parameters": {"type": "object", "required": ["ifade"], "properties": {
            "ifade": {"type": "string", "description": "ör: 1250*1.18 veya (3.5**2)*pi"},
        }}}},
    {"type": "function", "function": {
        "name": "tarih_hesapla",
        "description": "Bir tarihe gün/hafta ekler veya iki tarih arasındaki gün farkını bulur; haftanın gününü verir. "
                       "Tarih ve gün hesabını kafadan yapma, bunu kullan.",
        "parameters": {"type": "object", "properties": {
            "baslangic": {"type": "string", "description": "YYYY-AA-GG veya 'bugün'"},
            "gun": {"type": "integer", "description": "Eklenecek gün (negatif olabilir)"},
            "hafta": {"type": "integer", "description": "Eklenecek hafta"},
            "bitis": {"type": "string", "description": "Fark hesabı için ikinci tarih (YYYY-AA-GG)"},
        }}}},
]


def _sistem_promptu(diger_sohbetler=()):
    parcalar = [f"""Sen Sonda'sın: internette araştırma yapan, titiz ve zeki bir Türkçe yapay zekâ asistanı.
Bugün: {bugun()}.

GÜNCELLİK: Eğitim verin eskidir. Güncel olaylar, sürümler, fiyatlar, kişilerin görevleri ve tarihler konusunda
kendi hafızana güvenme; web sonuçlarını esas al. Web sonuçları hafızanla çelişirse web sonuçları doğrudur.

ARAÇLAR:
- Sana verilen web sonuçları yetersizse web_ara ile farklı sorgular dene (Türkçe + İngilizce varyant).
- Özetler yetmiyorsa farklı sitelerden en iyi 3-6 sonucu sayfa_oku ile oku.
- Her aritmetik işlemde hesapla aracını, her tarih/gün hesabında tarih_hesapla aracını kullan. Kafadan hesaplama.

DOĞRULUK:
- Sorunun öncülü yanlışsa (var olmayan ödül, kişi, ürün, olay) bunu açıkça söyle; uydurma bilgi üretme.
- Bulamadığın veya emin olmadığın bilgiyi "bulamadım" diye belirt. Kaynaklar çelişiyorsa belirt.
- Sayılar ve tarihler için mümkünse en az iki kaynakla doğrula.
- Tuzak sorulara dikkat et: soruyu harfiyen oku, sayma ve karşılaştırma işlerini adım adım yap.

BİÇİM:
- Webden aldığın her bilginin sonuna kaynak numarasını köşeli parantezle yaz: [1], [2][3].
- Kullanıcının biçim isteklerine (madde sayısı, uzunluk, dil, tablo) harfiyen uy.
- Cevabı her zaman Türkçe (kullanıcı başka dil istemedikçe) ve düzenli Markdown ile yaz:
  önce kısa ve net cevap, sonra gerekirse ayrıntılar. Gereksiz uzatma.
- Önceki konuşmayı dikkate al: "o", "bunu", "peki fiyatı" gibi ifadeler önceki mesajlara atıftır."""]
    hafiza_metni = hafiza.istem_metni()
    if hafiza_metni:
        parcalar.append(hafiza_metni + "\nBu bilgileri gerektiğinde doğal şekilde kullan; her cevapta tekrarlama.")
    if diger_sohbetler:
        parcalar.append("KULLANICININ DİĞER SOHBETLERİNİN BAŞLIKLARI (en yeniden eskiye):\n"
                        + "\n".join(f"- {b}" for b in diger_sohbetler[:15]))
    return "\n\n".join(parcalar)


ON_KARAR_PROMPTU = """Bugün {tarih}. Kullanıcının son mesajını analiz et. Sadece JSON döndür:
{{"arama": true/false, "haber": true/false, "zor": true/false, "sorgular": ["Türkçe sorgu", "English query"]}}
- arama: Selamlaşma, teşekkür, sohbet, çeviri, yazı düzeltme/yazma, kod yazma, saf matematik/mantık bulmacası veya
  sadece önceki cevabı yeniden düzenleme isteğiyse false. Tarih/gün hesabı da false: "bugünden 100 gün sonra",
  "X tarihine kaç gün kaldı", "iki tarih arası kaç gün", "X tarihi haftanın hangi günü" (bunlar tarih aracıyla
  kesin hesaplanır; web sitelerindeki sayılar başka günde hesaplanmış olabilir). Bilgi, olay, ürün, kişi, fiyat, tarih, tavsiye, karşılaştırma
  veya herhangi bir gerçek içeren her soruda true. Emin değilsen true.
- haber: Son günlerin/haftaların olayları soruluyorsa true.
- zor: Çok adımlı mantık, matematik problemi, bulmaca, tuzak soru, kod hata ayıklama veya dikkatli akıl yürütme
  gerektiriyorsa true.
- sorgular: 2 kısa arama sorgusu (biri Türkçe, biri İngilizce). Önceki konuşmadaki zamirleri açık hale getir
  (ör. önceki konu iPhone 18 ise "peki fiyatı?" -> "iPhone 18 fiyatı")."""

ONERI_PROMPTU = """Aşağıdaki soru ve cevaba göre kullanıcının sorabileceği 3 kısa, merak uyandıran takip sorusu üret.
Her biri en fazla 12 kelime, Türkçe. Sadece JSON: {{"oneriler": ["...", "...", "..."]}}

SORU: {soru}
CEVAP: {cevap}"""

HAFIZA_PROMPTU = """Kullanıcının mesajından, GELECEKTEKİ sohbetlerde işe yarayacak kalıcı kişisel bilgileri çıkar:
isim, meslek, şehir, aile, ilgi alanları, tercihler, sahip olduğu şeyler, üzerinde çalıştığı projeler, hedefler,
veya kullanıcının açıkça "hatırla" dediği şeyler. Genel bilgi soruları, tek seferlik istekler bilgi DEĞİLDİR.
Her bilgiyi üçüncü şahıs, kısa bir cümle olarak yaz (ör. "Kullanıcının adı Ayşe."). Çoğu mesajda boş liste döner.
Sadece JSON: {{"bilgiler": []}}

ZATEN BİLİNENLER:
{bilinen}

KULLANICI MESAJI: {mesaj}"""

# Birinci şahıs ifadeleri: hafıza çıkarımı sadece bunlar varsa çalışır (gereksiz model çağrısını önler)
_KISISEL = re.compile(r"\b(ben|benim|bana|beni|bende|adım|ismim|hatırla|unutma|bizim|eşim|oğlum|kızım)\b|"
                      r"\w+(ıyorum|iyorum|uyorum|üyorum|yorum|dım|dim|dum|düm|tım|tim|tum|tüm|ım|im|um|üm)\b",
                      re.IGNORECASE)


class Kaynaklar:
    """Numaralı kaynak listesi. Takip sorularında önceki cevabın kaynakları aynı numarayla korunur."""

    def __init__(self, onceki=()):
        self.liste, self._no = [], {}
        self.onceki = {int(k["no"]): k for k in onceki if k.get("url")}
        for k in self.onceki.values():
            self._no[k["url"]] = int(k["no"])
        self._sonraki = max(self.onceki, default=0) + 1

    def ekle(self, url, baslik):
        """Kaynağın numarasını döner; bu cevapta yeniyse ayrıca olay da döner."""
        if url in self._no:
            no = self._no[url]
            if no in self.onceki and not any(k["no"] == no for k in self.liste):
                return no, self._kaydet(no, url, self.onceki[no].get("baslik", baslik))
            return no, None
        no = self._sonraki
        self._sonraki += 1
        self._no[url] = no
        return no, self._kaydet(no, url, baslik)

    def _kaydet(self, no, url, baslik):
        kayit = {"no": no, "url": url, "baslik": baslik, "alan": alan_adi(url)}
        self.liste.append(kayit)
        return {"tur": "kaynak", **kayit}

    def atiflari_ekle(self, metin):
        """Cevapta atıf yapılan önceki kaynakları bu cevabın listesine ekler."""
        for n in sorted({int(x) for x in re.findall(r"\[(\d{1,3})\]", metin)}):
            if n in self.onceki and not any(k["no"] == n for k in self.liste):
                yield self._kaydet(n, self.onceki[n]["url"], self.onceki[n].get("baslik", ""))


BOS_ARAMA = ("ARAMA SONUÇ VERMEDİ. web_ara ile farklı sorgular dene. Yine bulamazsan güncel olaylar, sonuçlar, "
             "fiyatlar ve sürümler hakkında kendi hafızandan bilgi VERME (eğitim verin eskidir; olay çoktan olmuş "
             "olabilir). Bilgiyi bulamadığını açıkça söyle.")


ARAMA_CALISMIYOR = ("Şu an web aramasından sonuç alamadım; arama motorları geçici olarak yanıt vermiyor olabilir. "
                    "Bu soru güncel bilgi gerektirdiği için eski bilgimle tahmin yürütmek istemiyorum. "
                    "Birkaç saniye sonra tekrar sorar mısın?")


def _arama_olayi(sorgular, haber, sonuc_sayisi=None):
    olay = {"tur": "adim", "tip": "ara", "metin": " | ".join(sorgular), "haber": haber}
    if sonuc_sayisi is not None:
        olay["not"] = f"{sonuc_sayisi} sonuç, {len(set(sorgular))} sorgu × 3 motor"
    return olay


def _arac_calistir(ad, arg, soru, kaynaklar):
    """(model için metin sonuç, arayüz olayları) döner."""
    olaylar = []
    if ad == "web_ara":
        sorgular = arg.get("sorgular") or arg.get("sorgu") or soru
        if isinstance(sorgular, str):
            sorgular = [sorgular]
        sorgular = [str(s) for s in sorgular if str(s).strip()][:3] or [soru]
        haber = bool(arg.get("haber", False))
        sonuclar = web_ara(sorgular, soru=soru, adet=10, haber=haber)
        olaylar.append(_arama_olayi(sorgular, haber, len(sonuclar)))
        satirlar = []
        for r in sonuclar:
            no, olay = kaynaklar.ekle(r["url"], r["baslik"])
            if olay:
                olaylar.append(olay)
            tarih = f" ({r['tarih']})" if r.get("tarih") else ""
            satirlar.append(f"[{no}] {r['baslik']}{tarih}\n{r['url']}\n{r['ozet']}")
        return "\n\n".join(satirlar) or BOS_ARAMA, olaylar

    if ad == "sayfa_oku":
        urller = [u for u in arg.get("urller", []) if isinstance(u, str) and u.startswith("http")][:6]
        olaylar.append({"tur": "adim", "tip": "oku", "metin": ", ".join(alan_adi(u) for u in urller)})
        parcalar = []
        for s in sayfalari_oku(urller, soru, adet=4):
            no, olay = kaynaklar.ekle(s["url"], s["baslik"])
            if olay:
                olaylar.append(olay)
            icerik = "\n...\n".join(s["parcalar"]) or f"(okunamadı: {s.get('hata', 'metin yok')})"
            parcalar.append(f"[{no}] {s['baslik']}\n{icerik}")
        return "\n\n---\n\n".join(parcalar) or "Okunacak adres verilmedi.", olaylar

    if ad == "hesapla":
        sonuc = hesapla(str(arg.get("ifade", "")))
        olaylar.append({"tur": "adim", "tip": "hesap", "metin": sonuc})
        return sonuc, olaylar

    if ad == "tarih_hesapla":
        sonuc = tarih_hesapla(arg.get("baslangic") or "bugün", arg.get("gun") or 0,
                              arg.get("hafta") or 0, arg.get("bitis"))
        olaylar.append({"tur": "adim", "tip": "hesap", "metin": sonuc})
        return sonuc, olaylar

    return f"Bilinmeyen araç: {ad}", olaylar


def _json_sor(model, sistem, kullanici=None):
    mesajlar = [{"role": "system", "content": sistem}]
    if kullanici:
        mesajlar.append({"role": "user", "content": kullanici})
    yanit = ollama.chat(model=model, format="json", think=False, options=JSON_SECENEKLERI, messages=mesajlar)
    try:
        veri = json.loads(yanit.message.content)
        return veri if isinstance(veri, dict) else {}
    except json.JSONDecodeError:
        return {}


def _gecmisi_hazirla(gecmis, onceki_kaynaklar):
    """Uzun mesajları kısaltır; son cevabın kaynak listesini modele görünür yapar."""
    hazir = [{"role": m["role"], "content": m["content"][:4000]} for m in gecmis[-10:]]
    if onceki_kaynaklar and hazir and hazir[-1]["role"] == "assistant":
        liste = "\n".join(f"[{k['no']}] {k.get('baslik', '')} ({k['url']})" for k in onceki_kaynaklar[:30])
        hazir[-1]["content"] += f"\n\n(Bu cevabın kaynakları:\n{liste})"
    return hazir


def hizli(soru, gecmis, model, onceki_kaynaklar=(), diger_sohbetler=()):
    kaynaklar = Kaynaklar(onceki_kaynaklar)
    gecmis = _gecmisi_hazirla(gecmis, onceki_kaynaklar)
    mesajlar = [{"role": "system", "content": _sistem_promptu(diger_sohbetler)}, *gecmis,
                {"role": "user", "content": soru}]

    # 1) Arama kararını modele bırakmadan orkestratör verir: model eski bilgisiyle cevaplamasın
    son = "\n".join(f"{m['role']}: {m['content'][:400]}" for m in gecmis[-4:])
    karar = _json_sor(model, ON_KARAR_PROMPTU.format(tarih=bugun()),
                      f"Önceki konuşma:\n{son or '(yok)'}\n\nSon mesaj: {soru}")
    dusunme = bool(karar.get("zor"))
    if karar.get("arama", True):
        sorgular = [q for q in karar.get("sorgular", []) if isinstance(q, str) and q.strip()][:3] or [soru]
        arg = {"sorgular": sorgular, "haber": bool(karar.get("haber"))}
        arama_sonucu, olaylar = _arac_calistir("web_ara", arg, soru, kaynaklar)
        yield from olaylar
        # En iyi sonuçları doğrudan oku: özetler çoğu zaman ayrıntı için yetersiz
        en_iyiler = [k["url"] for k in kaynaklar.liste[:4]]
        if not en_iyiler:
            # Model, boş aramada uyarılara rağmen eski bilgisiyle cevap uyduruyor ("henüz oynanmadı" gibi).
            # web_ara zaten yeniden denedi; sonuç yoksa model çağrılmadan dürüstçe söylenir.
            yield {"tur": "token", "metin": ARAMA_CALISMIYOR}
            yield {"tur": "cevap_bitti", "metin": ARAMA_CALISMIYOR}
            return
        okuma_sonucu, olaylar = _arac_calistir("sayfa_oku", {"urller": en_iyiler}, soru, kaynaklar)
        yield from olaylar
        mesajlar.append({"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "web_ara", "arguments": arg}},
            {"function": {"name": "sayfa_oku", "arguments": {"urller": en_iyiler}}}]})
        mesajlar.append({"role": "tool", "content": arama_sonucu[:12000], "tool_name": "web_ara"})
        mesajlar.append({"role": "tool", "content": okuma_sonucu[:16000] or "(okunacak sayfa yok)",
                         "tool_name": "sayfa_oku"})
    yield from _dongu(mesajlar, soru, model, dusunme, kaynaklar)


def _dongu(mesajlar, soru, model, dusunme, kaynaklar):
    """Ajan döngüsü: model gerekirse ek arama, okuma veya hesap yapar."""
    for tur in range(MAKS_ARAC_TURU + 1):
        son_tur = tur == MAKS_ARAC_TURU
        akis = ollama.chat(model=model, messages=mesajlar, stream=True, think=dusunme,
                           tools=None if son_tur else ARACLAR, options=SECENEKLER)
        icerik, cagrilar, dusundu = "", [], False
        for parca in akis:
            if getattr(parca.message, "thinking", None) and not dusundu:
                dusundu = True
                yield {"tur": "adim", "tip": "dusun", "metin": "Adım adım akıl yürütüyor"}
            if parca.message.content:
                icerik += parca.message.content
                yield {"tur": "token", "metin": parca.message.content}
            if parca.message.tool_calls:
                cagrilar.extend(parca.message.tool_calls)
        if not cagrilar:
            yield from kaynaklar.atiflari_ekle(icerik)
            yield {"tur": "cevap_bitti", "metin": icerik}
            return
        if icerik:
            yield {"tur": "sifirla"}
        mesajlar.append({"role": "assistant", "content": icerik, "tool_calls": [
            {"function": {"name": c.function.name, "arguments": dict(c.function.arguments)}}
            for c in cagrilar]})
        for c in cagrilar:
            sonuc, olaylar = _arac_calistir(c.function.name, dict(c.function.arguments), soru, kaynaklar)
            yield from olaylar
            mesajlar.append({"role": "tool", "content": sonuc[:16000], "tool_name": c.function.name})


def _oneriler(model, soru, cevap):
    if len(cevap) < 80:
        return
    veri = _json_sor(model, ONERI_PROMPTU.format(soru=soru, cevap=cevap[:3000]))
    oneriler = [o for o in veri.get("oneriler", []) if isinstance(o, str) and o.strip()][:3]
    if oneriler:
        yield {"tur": "oneriler", "liste": oneriler}


def _hafizayi_guncelle(model, mesaj):
    """Arka planda çalışır: kullanıcının mesajından kalıcı bilgi çıkarıp hafızaya ekler."""
    if not _KISISEL.search(mesaj):
        return
    try:
        bilinen = "\n".join(f"- {b['metin']}" for b in hafiza.yukle()) or "(yok)"
        veri = _json_sor(model, HAFIZA_PROMPTU.format(bilinen=bilinen, mesaj=mesaj[:2000]))
        bilgiler = [b for b in veri.get("bilgiler", []) if isinstance(b, str) and 5 < len(b) < 200][:5]
        if bilgiler:
            hafiza.ekle(bilgiler)
    except Exception:
        pass


def baslik_uret(model, soru):
    veri = _json_sor(model, 'Kullanıcının ilk mesajı için 2-5 kelimelik Türkçe bir sohbet başlığı yaz. '
                            'Sadece JSON: {"baslik": "..."}', soru)
    baslik = str(veri.get("baslik", "")).strip().strip('"')
    return baslik[:60] or soru[:60]


PLAN_PROMPTU = """Bugün {tarih}. Kullanıcının araştırma sorusunu internette araştırılacak 4-5 alt soruya böl.
Her alt soru farklı bir yönü kapsasın (tanım, güncel veriler, maliyet/rakamlar, karşılaştırma, riskler vb.).
Her biri için bir Türkçe ve bir İngilizce kısa arama sorgusu yaz. Sadece JSON döndür:
{{"alt_sorular": [{{"soru": "...", "sorgu": "Türkçe sorgu", "sorgu_en": "English query", "haber": false}}]}}"""

EKSIK_PROMPTU = """Bugün {tarih}. Kullanıcının sorusu ve şu ana kadar toplanan bulguların başlıkları aşağıda.
Soruyu tam cevaplamak için hâlâ eksik veya doğrulanması gereken en önemli 0-3 noktayı belirle.
Sadece JSON döndür: {{"eksikler": [{{"soru": "...", "sorgu": "Türkçe sorgu", "sorgu_en": "English query"}}]}}
Bulgular yeterliyse boş liste döndür.

SORU: {soru}

BULGU ÖZETLERİ:
{ozet}"""

RAPOR_PROMPTU = """Sen Sonda'sın, titiz bir araştırma asistanı. Bugün {tarih}.
Aşağıdaki web bulgularına dayanarak kullanıcının sorusuna kapsamlı bir Türkçe araştırma raporu yaz.
- Başlangıçta 2-3 cümlelik bir özet ver, sonra ## başlıklarla bölümlere ayır. Uygunsa karşılaştırma tablosu kullan.
- Her bilginin sonuna kaynak numarasını köşeli parantezle yaz: [1], [2][3]. Sadece bulgulardaki bilgiyi kullan.
- Rakamları birden çok kaynak destekliyorsa hepsini göster; kaynaklar çelişiyorsa açıkça belirt.
- İngilizce kaynaklardaki bilgiyi Türkçeye çevirerek aktar.
- Eksik kalan noktaları sonda "Açık kalan sorular" başlığıyla yaz.
{hafiza}
BULGULAR:
{bulgular}"""


def _alt_sorulari_arastir(liste, kaynaklar, okunan, bulgular):
    for p in liste:
        sorgular = [s for s in (p.get("sorgu"), p.get("sorgu_en")) if isinstance(s, str) and s.strip()]
        if not sorgular:
            continue
        haber = bool(p.get("haber"))
        alt_soru = p.get("soru") or sorgular[0]
        sonuclar = web_ara(sorgular, soru=alt_soru, adet=8, haber=haber)
        yield _arama_olayi(sorgular, haber, len(sonuclar))

        yeni = [r["url"] for r in sonuclar if r["url"] not in okunan][:5]
        okunan.update(yeni)
        if yeni:
            yield {"tur": "adim", "tip": "oku", "metin": ", ".join(alan_adi(u) for u in yeni)}
        sayfalar = {s["url"]: s for s in sayfalari_oku(yeni, alt_soru, adet=3)}
        for r in sonuclar[:6]:
            sayfa = sayfalar.get(r["url"], {})
            parcalar = sayfa.get("parcalar") or [r["ozet"]]
            if not any(len(x) > 40 for x in parcalar):
                continue
            no, olay = kaynaklar.ekle(r["url"], r["baslik"])
            if olay:
                yield olay
            bulgular.append({"no": no, "baslik": r["baslik"], "alt_soru": alt_soru,
                             "metin": "\n...\n".join(parcalar), "tam": bool(sayfa.get("parcalar"))})


def derin(soru, gecmis, model, onceki_kaynaklar=(), diger_sohbetler=()):
    kaynaklar, okunan, bulgular = Kaynaklar(onceki_kaynaklar), set(), []
    gecmis = _gecmisi_hazirla(gecmis, onceki_kaynaklar)
    baglam = "\n".join(f"{m['role']}: {m['content'][:400]}" for m in gecmis[-4:])
    istek = f"Önceki konuşma:\n{baglam}\n\nAraştırma sorusu: {soru}" if baglam else soru

    yield {"tur": "adim", "tip": "plan", "metin": "Araştırma planı hazırlanıyor"}
    plan = _json_sor(model, PLAN_PROMPTU.format(tarih=bugun()), istek).get("alt_sorular", [])
    plan = [p for p in plan if isinstance(p, dict) and p.get("sorgu")][:5] or [{"soru": soru, "sorgu": soru}]
    yield {"tur": "adim", "tip": "plan", "metin": f"{len(plan)} alt soru",
           "detay": [p.get("soru", p["sorgu"]) for p in plan]}
    yield from _alt_sorulari_arastir(plan, kaynaklar, okunan, bulgular)

    # İkinci tur: eksik kalan noktaları bul ve ek arama yap
    ozet = "\n".join(f"- {b['alt_soru']}: {b['baslik']}" for b in bulgular)[:6000]
    eksikler = _json_sor(model, EKSIK_PROMPTU.format(tarih=bugun(), soru=soru, ozet=ozet)).get("eksikler", [])
    eksikler = [e for e in eksikler if isinstance(e, dict) and e.get("sorgu")][:3]
    if eksikler:
        yield {"tur": "adim", "tip": "plan", "metin": f"Eksik bilgi turu: {len(eksikler)} ek soru",
               "detay": [e.get("soru", e["sorgu"]) for e in eksikler]}
        yield from _alt_sorulari_arastir(eksikler, kaynaklar, okunan, bulgular)

    # Tam okunan sayfalar önce, sonra sadece özeti olanlar
    bulgular.sort(key=lambda b: not b["tam"])
    metin = "\n\n".join(f"[{b['no']}] {b['baslik']} (konu: {b['alt_soru']})\n{b['metin']}" for b in bulgular)
    yield {"tur": "adim", "tip": "yaz", "metin": f"{len(kaynaklar.liste)} kaynaktan rapor yazılıyor"}
    hafiza_metni = hafiza.istem_metni()
    sistem = RAPOR_PROMPTU.format(tarih=bugun(), bulgular=metin[:60000],
                                  hafiza=f"\n{hafiza_metni}\n" if hafiza_metni else "")
    akis = ollama.chat(model=model, stream=True, think=False, options=SECENEKLER,
                       messages=[{"role": "system", "content": sistem}, *gecmis[-4:],
                                 {"role": "user", "content": soru}])
    rapor = ""
    for parca in akis:
        if parca.message.content:
            rapor += parca.message.content
            yield {"tur": "token", "metin": parca.message.content}
    yield {"tur": "cevap_bitti", "metin": rapor}


def calistir(soru, gecmis, model, mod, onceki_kaynaklar=(), diger_sohbetler=(), oneri=True):
    basla = time.time()
    cevap = ""
    try:
        if mod == "gorev":
            import gorev  # geç içe aktarma: gorev.py agent.py'den içe aktarır
            uretec, oneri = gorev.calistir(soru, model, gecmis), False
        else:
            uretec = (derin if mod == "derin" else hizli)(soru, gecmis, model, onceki_kaynaklar, diger_sohbetler)
        for olay in uretec:
            if olay["tur"] == "cevap_bitti":
                cevap = olay["metin"]
                continue
            yield olay
        yield {"tur": "bitti", "sure": round(time.time() - basla, 1)}
        if oneri:
            yield from _oneriler(model, soru, cevap)
    except Exception as e:
        yield {"tur": "hata", "metin": f"{type(e).__name__}: {e}"}
    finally:
        threading.Thread(target=_hafizayi_guncelle, args=(model, soru), daemon=True).start()
