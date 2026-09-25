"""Görev modunun sınırları ve süreleri. Diğer modüller bunları ayar.X diye okur (testler değiştirebilsin)."""



MAKS_ADIM = 80


ADIM_SINIRI = {"basit": 25, "orta": 45, "derin": 80}


BEKLEME_SURESI = 15 * 60


GECMIS_ADIM = 8


MAKS_OGE = 150


HAFIZA_SAYFA = 25


TAKILMA_EKRAN, TAKILMA_DEVRET = 3, 4


BITIR_RED_SINIRI = 2


# Beklerken boş olay: arayüz koptuysa sunucu yazarken fark eder ve akışı kapatır (yoksa kuyruk kilitlenir)
NABIZ_ARALIGI = 5


TAM_GORULDU = 90


IKI_ADIM_KONTROL = 2  # saniye: kullanıcı doğrulamayı bitirdi mi diye sayfaya bakma aralığı


SAYFA_METNI = 8000  # sayfa başına biriktirilen görülen metin (karakter)
SONUC_ICERIK = 15000  # son cevaba giden görülen içerik (karakter)
CAPTCHA_BEKLE = 3  # saniye: onay kutusundan sonra resimli bulmaca çıktı mı diye bekleme

EYLEMLER = {"git": ["url"], "tikla": ["no"], "yaz": ["no", "metin"], "sec": ["no", "deger"], "kaydir": [],
            "geri": [], "bak": [], "oku": [], "not_al": ["metin"], "sana_birak": ["sebep"], "bitir": [], "captcha": []}
