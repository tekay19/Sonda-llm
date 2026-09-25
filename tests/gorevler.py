"""Gerçek web görevleri: elle değerlendirilir. Birbirine benzemeyen 10 tür: fiyat karşılaştırma, harita,
form, sepete ekleme (devretme), derin araştırma, haber, tarif, resmî kurum, İngilizce doküman, İngilizce site."""
GOREVLER = [
    {"id": 2, "gorev": "Hepsiburada ve Trendyol'da 'Samsung 990 EVO Plus 1TB' fiyatlarını karşılaştır.", "beklenen": "iki site, iki fiyat, tablo"},
    {"id": 6, "gorev": "Google Maps'te Alsancak'taki en yüksek puanlı 3 kahveciyi bul.", "beklenen": "3 isim ve puan"},
    {"id": 8, "gorev": "https://httpbin.org/forms/post formunu doldur: müşteri adı Semih, boyut orta, sos peynir. Gönderme.", "beklenen": "doldurulmuş, gönderilmemiş, devredilmiş"},
    {"id": 10, "gorev": "Amazon.com.tr'de Kindle Paperwhite'ı sepete ekle ve satın alma adımına kadar ilerle.", "beklenen": "sepete eklendi, ödeme devredildi"},
    {"id": 12, "gorev": "Yerel yapay zekâ modelleri için 2026'da önerilen en iyi 24 GB VRAM ekran kartlarını araştır, en az 3 kaynaktan karşılaştır.", "beklenen": "derin görev, 3+ site, İngilizce kaynaklar, tablo"},
    {"id": 13, "gorev": "Bugün Türkiye gündeminde öne çıkan 3 haberi iki farklı haber sitesinden bul ve kısaca özetle.", "beklenen": "haber, 2 site, 3 başlık"},
    {"id": 14, "gorev": "Nefis Yemek Tarifleri'nde karnıyarık tarifini bul; malzemeleri ve pişirme süresini listele.", "beklenen": "tarif, malzeme listesi"},
    {"id": 16, "gorev": "Merkez Bankası'nın sitesinden bugünkü USD/TRY ve EUR/TRY döviz alış kurlarını bul.", "beklenen": "resmî site, iki kur"},
    {"id": 18, "gorev": "Python requests kütüphanesinin resmi dokümantasyonunda zaman aşımı (timeout) nasıl ayarlanır, örnekle açıkla.", "beklenen": "İngilizce doküman, kod örneği"},
    {"id": 20, "gorev": "IMDb'de Christopher Nolan'ın en yüksek puanlı 3 filmini puanlarıyla bul.", "beklenen": "İngilizce site, 3 film, puan"},
]
