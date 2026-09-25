"""Modelin çağırabildiği araçlar: web araması, sayfa okuma, hesap ve tarih."""
from ..hesap import hesapla, tarih_hesapla
from ..web import alan_adi, sayfalari_oku, web_ara
from .promptlar import BOS_ARAMA


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


def arama_olayi(sorgular, haber, sonuc_sayisi=None):
    olay = {"tur": "adim", "tip": "ara", "metin": " | ".join(sorgular), "haber": haber}
    if sonuc_sayisi is not None:
        olay["not"] = f"{sonuc_sayisi} sonuç, {len(set(sorgular))} sorgu × 3 motor"
    return olay


def arac_calistir(ad, arg, soru, kaynaklar):
    """(model için metin sonuç, arayüz olayları) döner."""
    olaylar = []
    if ad == "web_ara":
        sorgular = arg.get("sorgular") or arg.get("sorgu") or soru
        if isinstance(sorgular, str):
            sorgular = [sorgular]
        sorgular = [str(s) for s in sorgular if str(s).strip()][:3] or [soru]
        haber = bool(arg.get("haber", False))
        sonuclar = web_ara(sorgular, soru=soru, adet=10, haber=haber)
        olaylar.append(arama_olayi(sorgular, haber, len(sonuclar)))
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
