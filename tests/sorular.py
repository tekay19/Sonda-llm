"""Sonda zorlu test seti: 50 soru.

Her test:
  turlar : sırayla sorulan mesajlar (son tur puanlanır, öncekiler sohbet geçmişi olur)
  hepsi  : cevapta HEPSİ bulunması gereken düzenli ifadeler (büyük/küçük harf duyarsız)
  yasak  : cevapta HİÇBİRİ bulunmaması gereken ifadeler
  manuel : otomatik kontrol edilemez, insan değerlendirir
  yeni_sohbet : True ise geçmiş olmadan (hafıza testi için)
"""

TESTLER = [
    # ---- sayma ve tuzak sorular
    {"id": 1, "kat": "tuzak", "turlar": ["\"strawberry\" kelimesinde kaç tane r harfi var?"], "hepsi": [r"\b3\b|üç"]},
    {"id": 2, "kat": "tuzak", "turlar": ["\"Kırkayak\" kelimesinde kaç tane k harfi var? Büyük küçük fark etmez."], "hepsi": [r"\b3\b|üç"]},
    {"id": 3, "kat": "tuzak", "turlar": ["9.11 mi daha büyük yoksa 9.9 mu?"], "hepsi": [r"9[.,]9\b.{0,40}(büyük|daha)|büyük olan.{0,20}9[.,]9\b"], "yasak": [r"9[.,]11.{0,15}daha büyük"]},
    {"id": 4, "kat": "tuzak", "turlar": ["Bir çiftçinin 17 koyunu var. 9'u hariç hepsi ölüyor. Kaç koyunu kaldı?"], "hepsi": [r"\b9\b|dokuz"], "yasak": [r"\b8\b koyun"]},
    {"id": 5, "kat": "tuzak", "turlar": ["Ali'nin 3 kız kardeşi var. Her kız kardeşinin 1 erkek kardeşi var. Ali'nin kaç erkek kardeşi var?"], "hepsi": [r"\b0\b|hiç|sıfır|yok"]},
    {"id": 6, "kat": "tuzak", "turlar": ["Bir sopa ile bir top toplam 1,10 TL. Sopa toptan tam 1 TL daha pahalı. Top kaç TL?"], "hepsi": [r"0[.,]05|5 kuruş"], "yasak": [r"top.{0,20}\b0[.,]10\b"]},
    {"id": 7, "kat": "tuzak", "turlar": ["5 makine 5 ürünü 5 dakikada üretiyor. 100 makine 100 ürünü kaç dakikada üretir?"], "hepsi": [r"\b5 dakika|beş dakika"], "yasak": [r"100 dakika"]},
    {"id": 8, "kat": "tuzak", "turlar": ["Bir göldeki nilüferler her gün iki katına çıkıyor ve gölü 48 günde tamamen kaplıyor. Gölün yarısını kaç günde kaplar?"], "hepsi": [r"\b47\b"], "yasak": [r"\b24 gün"]},
    {"id": 9, "kat": "tuzak", "turlar": ["\"Ankara Türkiye'nin başkentidir\" cümlesinde kaç kelime var?"], "hepsi": [r"\b3\b|üç"]},
    {"id": 10, "kat": "tuzak", "turlar": ["Bir koşu yarışında ikinci sıradaki kişiyi geçtin. Şimdi kaçıncısın?"], "hepsi": [r"ikinci|2\."], "yasak": [r"birinci(siniz|sin)\b"]},

    # ---- kesin hesap
    {"id": 11, "kat": "hesap", "turlar": ["1'den 100'e kadar olan tam sayıların toplamı kaçtır?"], "hepsi": [r"5[.,]?050"]},
    {"id": 12, "kat": "hesap", "turlar": ["2 üzeri 32 kaçtır?"], "hepsi": [r"4[.,]?294[.,]?967[.,]?296"]},
    {"id": 13, "kat": "hesap", "turlar": ["37 çarpı 43 kaç eder?"], "hepsi": [r"1[.,]?591"]},
    {"id": 14, "kat": "hesap", "turlar": ["123456789 ile 987654321'i çarp, sonucu tam olarak yaz."], "hepsi": [r"121[.,]?932[.,]?631[.,]?112[.,]?635[.,]?269"]},
    {"id": 15, "kat": "hesap", "turlar": ["391'in karekökü kaçtır? Virgülden sonra 2 basamak ver."], "hepsi": [r"19[.,]77"]},
    {"id": 16, "kat": "hesap", "turlar": ["2400 TL'lik bir ürüne %20 KDV eklenirse toplam kaç TL olur?"], "hepsi": [r"2[.,]?880"]},
    {"id": 17, "kat": "hesap", "turlar": ["10.000 TL aylık %4 bileşik faizle 12 ay sonunda kaç TL olur? Kuruşa kadar yaz."], "hepsi": [r"16[.,]?010[.,]32"]},
    {"id": 18, "kat": "hesap", "turlar": ["Saatte 90 km hızla giden bir araç 315 km yolu kaç saat kaç dakikada alır?"], "hepsi": [r"3 saat 30 dakika|3[.,]5 saat"]},

    # ---- tarih hesabı (bugün 24 Eylül 2026 Perşembe)
    {"id": 19, "kat": "tarih", "turlar": ["Bugünden 100 gün sonra hangi tarih ve haftanın hangi günü olacak?"], "hepsi": [r"2 Ocak 2027|02\.01\.2027", r"Cumartesi"]},
    {"id": 20, "kat": "tarih", "turlar": ["29 Ekim 1923 haftanın hangi gününe denk gelir?"], "hepsi": [r"Pazartesi"]},
    {"id": 21, "kat": "tarih", "turlar": ["2100 yılı artık yıl mı?"], "hepsi": [r"hayır|değil|artık yıl değil"]},
    {"id": 22, "kat": "tarih", "turlar": ["Bugünün tarihi ne ve haftanın hangi günü?"], "hepsi": [r"24 Eylül 2026|24\.09\.2026", r"Perşembe"]},
    {"id": 23, "kat": "tarih", "turlar": ["1 Ocak 2027'ye kaç gün kaldı?"], "hepsi": [r"\b99\b"]},

    # ---- yanlış öncül ve uydurma tuzakları
    {"id": 24, "kat": "oncul", "turlar": ["2025 Nobel Matematik Ödülü'nü kim kazandı?"], "hepsi": [r"Nobel.{0,60}(yok|verilmez|bulunma|mevcut değil)|matematik (dalında|alanında)?.{0,30}Nobel.{0,40}(yok|verilmez|bulunma)"]},
    {"id": 25, "kat": "oncul", "turlar": ["Atatürk'ün 1950 yılında yaptığı meclis konuşmasını özetler misin?"], "hepsi": [r"1938"]},
    {"id": 26, "kat": "oncul", "turlar": ["Türkiye'nin 82. ili hangisidir?"], "hepsi": [r"81"]},
    {"id": 27, "kat": "oncul", "turlar": ["Einstein Nobel ödülünü görelilik teorisi için hangi yıl aldı?"], "hepsi": [r"fotoelektrik"]},
    {"id": 28, "kat": "oncul", "turlar": ["Everest Dağı'nın Türkiye'deki zirvesi kaç metredir?"], "hepsi": [r"Nepal|Himalaya|Türkiye'de (değil|bulunmaz|yer almaz)"]},
    {"id": 29, "kat": "oncul", "turlar": ["İnsanlar beyinlerinin sadece %10'unu kullandığı için geri kalanını nasıl aktive edebiliriz?"], "hepsi": [r"mit|efsane|yanlış|doğru değil"]},
    {"id": 30, "kat": "oncul", "turlar": ["Çin Seddi uzaydan çıplak gözle görülebilir mi?"], "hepsi": [r"hayır|görülemez|görülmez|mit|efsane"]},

    # ---- güncel bilgi (web araması şart)
    {"id": 31, "kat": "guncel", "turlar": ["Ollama'nın en son sürümü hangisi?"], "hepsi": [r"0\.3[4-9]"], "manuel": True},
    {"id": 32, "kat": "guncel", "turlar": ["2026 FIFA Dünya Kupası'nı hangi ülke kazandı?"], "yasak": [r"henüz (oynanmadı|başlamadı)"], "manuel": True},
    {"id": 33, "kat": "guncel", "turlar": ["Şu anda Türkiye Cumhuriyeti Cumhurbaşkanı kim?"], "manuel": True},
    {"id": 34, "kat": "guncel", "turlar": ["Bugün 1 ABD doları kaç Türk lirası?"], "hepsi": [r"\[\d+\]"], "manuel": True},
    {"id": 35, "kat": "guncel", "turlar": ["Apple'ın en son çıkan iPhone modeli hangisi?"], "hepsi": [r"iPhone 1[89]"], "manuel": True},
    {"id": 36, "kat": "guncel", "turlar": ["Qwen model ailesinin en yeni sürümü hangisi?"], "hepsi": [r"Qwen ?3\.[6-9]|Qwen ?4"], "manuel": True},
    {"id": 37, "kat": "guncel", "turlar": ["Bu hafta yapay zekâ dünyasında öne çıkan 3 haber nedir?"], "hepsi": [r"\[\d+\]"], "manuel": True},
    {"id": 38, "kat": "guncel", "turlar": ["TÜİK'e göre Türkiye'nin en güncel nüfusu kaç?"], "hepsi": [r"8[5-7][.,]\d|8[5-7] milyon"], "manuel": True},

    # ---- talimata uyma
    {"id": 39, "kat": "talimat", "turlar": ["Yapay zekâyı tam 3 madde ile anlat. Her madde en fazla 6 kelime olsun. Başka hiçbir şey yazma."], "madde_sayisi": 3, "maks_kelime": 6},
    {"id": 40, "kat": "talimat", "turlar": ["Sadece 'Evet' veya 'Hayır' diye cevap ver, başka hiçbir şey yazma: Dünya düz mü?"], "hepsi": [r"^\W*hayır\W*$"]},
    {"id": 41, "kat": "talimat", "turlar": ["Answer only in English, one sentence: What is the capital of Australia?"], "hepsi": [r"Canberra"], "yasak": [r"başkent"]},
    {"id": 42, "kat": "talimat", "turlar": ["\"Merhaba\" kelimesini harf harf tersten yaz."], "hepsi": [r"abahrem"]},
    {"id": 43, "kat": "talimat", "turlar": ["Türkiye'nin nüfusça en büyük 3 şehrini sadece JSON dizisi olarak ver, açıklama yazma."], "hepsi": [r"^\s*(```(json)?\s*)?\[", r"İstanbul", r"Ankara", r"İzmir"]},

    # ---- kod
    {"id": 44, "kat": "kod", "turlar": ["Bu Python kodundaki hata ne? for i in range(10) print(i)"], "hepsi": [r"iki nokta|:"]},
    {"id": 45, "kat": "kod", "turlar": ["Python'da bir listeyi tek satırda tersine çevirmenin en kısa yolu nedir?"], "hepsi": [r"\[::-1\]"]},

    # ---- çok turlu: takip soruları ve hafıza
    {"id": 46, "kat": "takip", "turlar": ["Türkiye'nin nüfusça en kalabalık 3 şehri hangileri?", "Bunlardan ikincisinin plaka kodu kaç?"], "hepsi": [r"\b06\b|\b6\b"]},
    {"id": 47, "kat": "takip", "turlar": ["Aklımdan bir sayı tuttum: 7. Bunu bu sohbette hatırla.", "Tuttuğum sayının küpü kaç?"], "hepsi": [r"343"]},
    {"id": 48, "kat": "takip", "turlar": ["iPhone 18 Pro ne zaman piyasaya çıktı?", "Peki ABD'deki başlangıç fiyatı ne kadar?"], "hepsi": [r"\$|dolar|USD"], "manuel": True},
    {"id": 49, "kat": "hafiza", "turlar": ["Benim adım Deniz, İzmir'de yaşıyorum ve yazılım geliştiriciyim.", "Adım ne ve hangi şehirde yaşıyorum?"], "hepsi": [r"Deniz", r"İzmir"]},
    {"id": 50, "kat": "hafiza", "yeni_sohbet": True, "bekle": 20, "turlar": ["Benim adımı ve mesleğimi hatırlıyor musun?"], "hepsi": [r"Deniz", r"yazılım"]},
]

assert len(TESTLER) == 50 and len({t["id"] for t in TESTLER}) == 50
