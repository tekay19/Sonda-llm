# Gemini sağlayıcı desteği: yerel modele ek bulut seçeneği

*25 Eylül 2026 · Durum: onay bekliyor*

## Amaç

Sonda, yerel Ollama modellerine ek olarak Google Gemini API ile de çalışabilsin. Gemini'nin getirdikleri:
- Hız: görev adımı başına 1-3 sn. Yerel modelde bu süre 10-20 sn.
- Zekâ: planlama ve analiz kalitesi daha yüksek.

Yerel seçenek aynen kalır. Model, her sohbette arayüzdeki seçiciden seçilir.

**Kullanıcı kararları:**
- Gemini, yerel modelin **yerine değil, yanında** kullanılır.
- Görevde verilen şifre **hiçbir modele gitmez**. Bu kural hem Gemini hem yerel model için geçerlidir. Model yalnızca bir yer tutucu görür, gerçek şifreyi kod doldurur.
- **Sessiz geçiş yoktur.** Gemini hata verirse Sonda kendiliğinden yerel modele geçmez, durumu açıkça söyler.

**Başarı ölçütleri:**
- Gemini ile bütün modlar çalışır: hızlı, derin, görev ve görev modundaki yönlendirme.
- Mevcut testlerin hepsi yerel modelle aynen geçer.
- Gerçek şifre hiçbir istemde, kayıtta ya da olayda geçmez.
- API anahtarı hiçbir yanıtta ya da kayıtta görünmez.
- Upwork inceleme görevi Gemini ile yerel modele göre belirgin şekilde hızlı biter.

## Mimari

Yeni paket `sonda/model/`:

| Dosya | Görevi |
|---|---|
| `__init__.py` | Ortak arayüz: `sohbet(...)`, `modeller()`, `ModelHatasi`. Model adına göre sağlayıcıyı seçer. |
| `ollama_saglayici.py` | Mevcut davranış: Ollama istemcisi, zaman sınırıyla. |
| `gemini_saglayici.py` | Google'ın resmi `google-genai` kütüphanesiyle Gemini. Mesaj, görsel, araç ve JSON dönüşümleri, yeniden deneme, hata çevirisi. |
| `sonda/ayarlar.py` | API anahtarını `veri/ayarlar.json` dosyasında saklar. `GEMINI_API_KEY` ortam değişkeni yedek olarak okunur. |

**Model adı kuralı:** `gemini:` ile başlayan adlar Gemini'ye gider (örneğin `gemini:gemini-flash-latest`). Diğer bütün adlar Ollama'ya gider.

**Ortak arayüz:**

```
sohbet(model, mesajlar, akis=False, json=False, dusun=False, araclar=None, secenekler=None)
  akis=False -> Yanit(metin, arac_cagrilari)
  akis=True  -> Parca(metin, dusunce, arac_cagrilari) akışı
```

**Mesaj biçimi:** Bugünkü Ollama biçimi ortak iç biçim olarak kalır: `role` (system, user, assistant, tool), `content`, `images` (bayt), `tool_calls`, `tool_name`. Gemini sağlayıcısı bu biçimi şöyle çevirir:

| Ortak biçim | Gemini karşılığı |
|---|---|
| `system` | `system_instruction` |
| `user` / `assistant` | `user` / `model` rolleri |
| `images` | JPEG görsel parçası |
| `tool_calls` | `function_call` parçası |
| `tool` mesajı | `function_response` parçası |
| JSON çıktı | `response_mime_type="application/json"` |
| Düşünme | Düşünme ayarı. Kapalıyken bütçe en düşük değerde tutulur. |
| Araç tanımları (`ARACLAR`) | Fonksiyon tanımlarına çevrilir |

**Değişen yerler:** Model çağrısı yapılan 8 yerin hepsi `sonda.model.sohbet` kullanır:
- `ortak.json_sor`
- `arastirma/hizli.py` (araç döngüsü), `arastirma/derin.py`, `arastirma/sohbet.py`
- `gorev/karar.py` (3 çağrı)
- `gorev/dongu.py` (sonuç yazımı)

Sayfa sıralamasında kullanılan embedding modeli (`bge-m3`) yerelde kalır.

## Şifre yer tutucu (yerel ve Gemini)

- Görev başında `gizli_adaylar(gorev_metni)` ile bulunan her şifrenin yerine `{SIFRE_1}`, `{SIFRE_2}` gibi yer tutucular konur. Önceki mesajlardaki şifreler de aynı şekilde işlenir. Modele giden bütün istemler, görev kayıtları ve son cevap bu yer tutuculu metni kullanır.
- İstemde modele şu söylenir: *"Görevde verilen şifre {SIFRE_1} olarak gizlendi. Şifre alanına tam olarak {SIFRE_1} yaz; gerçek şifreyi Sonda doldurur."*
- **Koruma kuralı:** `yaz` eyleminin değeri tam olarak bir yer tutucuysa, alan bir şifre alanıysa ve site görevde adı geçen siteyse izin verilir. Kod, yazmadan hemen önce gerçek şifreyi koyar. Yer tutucu başka bir alanda ya da adreste geçerse işlem engellenir. Mevcut kurallar (sadece adı geçen site, kart/CVV/doğrulama kodu yasağı, sızıntı koruması) aynen geçerlidir.
- Arayüzde ve olaylarda şifre yine `•••` olarak gösterilir.

## API anahtarı

- Anahtar `veri/ayarlar.json` dosyasında saklanır. Bu dosya kullanıcının bilgisayarından çıkmaz ve repoya girmez. Arayüzden kaydedilen anahtar önceliklidir, `GEMINI_API_KEY` ortam değişkeni yedektir.
- **Uç noktalar:**
  - `GET /api/ayarlar` → `{"gemini": {"var": bool, "son4": "…abcd"}}`. Anahtarın tamamı hiçbir zaman dönmez.
  - `POST /api/ayarlar/gemini {"anahtar": "..."}` → Anahtar önce model listesi istenerek doğrulanır, geçerliyse kaydedilir. Geçersizse kaydedilmez ve anlaşılır bir mesaj döner.
  - `DELETE /api/ayarlar/gemini` → Anahtarı siler.
- Anahtar hiçbir kayda, hata mesajına ya da olaya yazılmaz. Hata metinleri, içinde anahtar geçme ihtimaline karşı temizlenir.

## Model listesi

- `/api/modeller` yerel modelleri bugünkü gibi listeler. Anahtar varsa Gemini modellerini de ekler:
  - "Gemini Flash (bulut, hızlı)"
  - "Gemini Pro (bulut, en akıllı)"
- **Model seçimi:** Google'ın model listesinde `gemini-flash-latest` / `gemini-pro-latest` takma adları varsa bunlar kullanılır. Yoksa metin üretebilen en yeni flash ve pro modelleri seçilir. Liste 1 saat önbellekte tutulur. Liste alınamazsa takma adlar yine gösterilir.
- Arayüzde bulut modelleri "(bulut)" etiketiyle görünür. Böylece verinin dışarı gittiği her zaman belli olur.

## Hata yönetimi

Bütün Gemini hataları, kullanıcıya gösterilecek Türkçe bir mesaj taşıyan `ModelHatasi`'na çevrilir:

| Durum | Davranış ya da mesaj |
|---|---|
| Geçersiz ya da yetkisiz anahtar | "Gemini anahtarı geçersiz ya da yetkisiz. Ayarlar'dan kontrol et." |
| İstek sınırı (429) | 3 kez artan beklemeyle yeniden denenir. Yine olmazsa: "Gemini istek sınırı/kotası doldu; biraz bekle ya da yerel modele geç." |
| Sunucu hatası (5xx) | Yeniden denenir. Yine olmazsa: "Gemini şu an yanıt vermiyor." |
| Ağ hatası | "Gemini'ye ulaşılamadı (internet bağlantısı?)." |
| Güvenlik filtresi | "Gemini bu içeriği yanıtlamadı (güvenlik filtresi)." |

- **Sohbet ve araştırmada:** Mevcut `hata` olayı kullanılır ve arayüzde bu mesaj görünür.
- **Görevde:** Görev "hata" durumuyla biter. Son cevap modelsiz yazılır: hata mesajı ve o ana kadar alınan notlar düz liste olarak verilir. Böylece notlar kaybolmaz.

## Arayüz

- Sol menüde "Hafıza"nın altına **"Ayarlar"** eklenir. Sağ çekmecede açılır ve şunları içerir:
  - Gemini API anahtarı alanı (şifre tipinde)
  - "Kaydet ve test et" ile "Sil" butonları
  - Kısa bir gizlilik notu: bulut model seçildiğinde ziyaret edilen sayfaların içeriği Google'a gider. Hesaplarla çalışırken ücretli katman önerilir.
- Model seçicide bulut modelleri "(bulut)" etiketiyle görünür.

## Testler

- **Sağlayıcı katmanı (birim):** Sahte bir Gemini istemcisiyle şunlar sınanır:
  - sistem mesajı, rol ve görsel dönüşümü
  - JSON modu
  - düşünme ayarı
  - akış parçaları
  - araç tanımı ve araç çağrısı / cevabı gidiş-dönüşü
  - hata çevirisi ve yeniden deneme
  - anahtarın hata metinlerinden temizlenmesi
- **Yönlendirme:** `gemini:` önekli adlar Gemini'ye, diğerleri Ollama'ya gider.
- **Geriye dönük uyum:** Mevcut testlerin hepsi yerel modelle geçer. Testlerin yamaladığı noktalar yeni katmana taşınır.
- **Şifre yer tutucu:**
  - İstemlerde ve kayıtlarda gerçek şifre yoktur.
  - Şifre alanına gerçek değer yazılır.
  - Yer tutucu başka bir alana ya da adrese yazılamaz.
  - Şifre, görevde adı geçmeyen bir sitede yazılamaz.
- **Anahtar:**
  - Kaydetme, doğrulama ve silme çalışır.
  - `GET /api/ayarlar` anahtarın tamamını döndürmez.
  - Anahtar yoksa Gemini modelleri listelenmez.
- **Gerçek Gemini (`-m gemini`):** Anahtar varsa çalışır, yoksa atlanır. Birer tane JSON, akış, araç ve görsel çağrısı, ayrıca yerel sahte sitede bir görev yapılır.
- **Gerçek dünya:** Upwork inceleme görevi Gemini ile çalıştırılır. Süre ve kalite, yerel modeldeki 22 dakikalık çalışmayla karşılaştırılır.

## Kapsam dışı (şimdilik)

- Gemini ile embedding (`bge-m3` yerel kalır)
- Karma kullanım (basit adımlar yerel, analiz bulut). Katman buna hazır, sonraki adım.
- Başka bulut sağlayıcılar (OpenAI, Claude). Katman eklemeye uygun.
- Maliyet takibi ve harcama sınırı
