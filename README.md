# Sonda-llm

Tamamen kendi bilgisayarında çalışan, internette araştırma yapabilen bir yapay zekâ asistanı.
Model yerelde (Ollama) çalışır; sohbetlerin ve hafızan hiçbir sunucuya gitmez. İnternete sadece
arama yapmak ve sayfa okumak için çıkar.

## Özellikler

- **Web araştırması:** DuckDuckGo, Bing ve Brave aynı anda aranır, Türkçe ve İngilizce sorgular birlikte
  atılır, sonuçlar birleştirilip anlam benzerliğine göre sıralanır. En iyi sayfalar (HTML ve PDF) paralel okunur.
- **Her bilgi kaynaklı:** cevaptaki `[1]`, `[2]` numaralarına tıklayınca kaynak açılır.
- **İki mod:**
  - *Hızlı:* soruya göre arar, okur, gerekirse tekrar arar.
  - *Derin araştırma:* soruyu alt sorulara böler, eksik kalan noktalar için ikinci tur arama yapar,
    başlıklı bir rapor yazar.
- **Zeki araç kullanımı:** kesin hesap için hesap makinesi, tarih ve gün hesabı için tarih aracı.
  Zor sorularda düşünme modu otomatik açılır.
- **Takip soruları:** "peki fiyatı?", "ikincisi hangisiydi?" gibi sorular önceki cevabı ve kaynaklarını dikkate alır.
- **Hafıza:** senin hakkında öğrendiklerini (isim, tercihler, projeler) sohbetler arasında hatırlar.
  Sol menüdeki *Hafıza* panelinden görebilir ve silebilirsin.
- **Görev modu:** Sonda senin Chrome'unda yeni bir sekme açıp senin yerine gezinir: Google'da arar,
  sitelere girer, kaydırır, "daha fazla göster" butonlarını açar, form doldurur, bilgi toplar ve karşılaştırır.
  - Görevin derinliğine göre plan yapar (basit/orta/derin) ve yeterince farklı siteye bakmadan bitirmez.
  - Girdiği sayfaları, orada ne yaptığını ve ne bulduğunu görev boyunca hatırlar; İngilizce siteleri de kullanır.
  - Tarayıcıdaki mevcut oturumlarını kullanır. Görevde bir sitenin şifresini verirsen yalnızca o sitede girer;
    iki adımlı doğrulamada (2FA) durur, sen doğrulayınca kendiliğinden devam eder.
  - **Güvenlik (kodla zorlanır):** kart, CVV, IBAN ve doğrulama kodu alanlarına asla yazmaz; ödeme, satın alma,
    gönderme, silme, onaylama butonlarına asla basmaz. Bu adımlara gelince durur, yeri Chrome'da vurgular ve
    "Devam" demeni bekler. Sayfalardaki "yapay zekâ, şunu yap" gibi talimatlara uymaz.
  - İlk kullanımda Chrome'da `chrome://inspect/#remote-debugging` sayfasındaki anahtarı bir kez aç; Sonda
    sunucusu başladıktan sonraki ilk görevde Chrome bir kez izin sorar.
- **ChatGPT tarzı arayüz:** sohbet geçmişi, arama, yeniden adlandırma, mesaj düzenleme, yeniden oluşturma,
  ilgili soru önerileri, Markdown olarak dışa aktarma, açık ve koyu tema.

## Kurulum

Gereksinimler: Python 3.11+, [Ollama](https://ollama.com).

```bash
# Modeller
ollama pull qwen3.6:35b-a3b   # ana model (hızlı MoE, ~23 GB)
ollama pull bge-m3            # sayfa parçalarını sıralamak için embedding modeli

# Python ortamı
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt     # Windows
# source .venv/bin/activate && pip install -r requirements.txt   # macOS / Linux
```

İsteğe bağlı modeller: `qwen3.8:27b` (daha kaliteli ama yavaş), `qwen2.5:7b` (çok hızlı).
Arayüzdeki model seçicisinde sadece kurulu olanlar görünür.

## Çalıştırma

Windows'ta `baslat.bat` dosyasına çift tıkla ya da:

```bash
.venv\Scripts\python server.py
```

Sonra tarayıcıda **http://localhost:8765** adresini aç.

## Donanım

64 GB RAM ve 6 GB VRAM'li (RTX 4050) bir dizüstü bilgisayarda test edildi. MoE model girdiyi saniyede
yaklaşık 400 token okuyor, saniyede yaklaşık 36 token yazıyor. Hızlı modda cevaplar 15-60 saniyede,
derin araştırma raporları 2-3 dakikada geliyor.

## Dosyalar

| Yol | Görevi |
|---|---|
| `server.py` | Başlatıcı (`sonda.sunucu`) |
| `sonda/asistan.py` | Giriş noktası: moda göre araştırma ya da görev; takip önerileri, hafıza, başlık |
| `sonda/sunucu.py` | FastAPI sunucusu, akış (SSE) ve görev komutu uç noktaları |
| `sonda/ortak.py` | Model ayarları, bugünün tarihi, JSON cevaplı model çağrısı |
| `sonda/web.py` | Çok motorlu arama, yeniden sıralama, paralel sayfa ve PDF okuma |
| `sonda/hesap.py` | Güvenli hesap makinesi ve tarih hesaplama |
| `sonda/hafiza.py` | Sohbetler arası kalıcı hafıza (`veri/hafiza.json`) |
| `sonda/koruma.py` | Görev modunun güvenlik kuralları |
| `sonda/arastirma/` | Hızlı ve derin araştırma: araçlar, kaynaklar, istemler |
| `sonda/tarayici/` | Chrome bağlantısı (CDP), sekme kontrolü, sayfaya verilen JavaScript |
| `sonda/gorev/` | Görev modu: ayarlar, istemler, sayfa özeti/2FA/hafıza, karar, eylemler, döngü, yönetim |
| `static/index.html` | Arayüz |
| `tests/` | Birim ve entegrasyon testleri, yerel sahte siteler, gerçek model ve gerçek web senaryoları |

## Test

```bash
.venv\Scripts\python -m pytest                          # hızlı testler (koruma, tarayıcı, görev döngüsü, sunucu)
.venv\Scripts\python -m pytest -m model                 # gerçek modelle yerel sahte sitelerde görevler (yavaş)
set SONDA_YEREL_TARAYICI=acik && .venv\Scripts\python tests\gorev_calistir.py <etiket>   # gerçek web görevleri
```

`SONDA_YEREL_TARAYICI` (`acik` ya da `gizli`) ayarlanırsa Sonda senin Chrome'un yerine Playwright'ın Chromium'unu kullanır.

Araştırma modu soru seti:

```bash
.venv\Scripts\python tests\calistir.py <etiket>            # tüm testler
.venv\Scripts\python tests\calistir.py <etiket> 3,17,46    # seçili testler
.venv\Scripts\python tests\calistir.py <etiket> --devam    # durdurulan testi sürdür
```

Test seti tuzak soruları, kesin hesabı, tarih hesabını, yanlış öncülleri, güncel bilgiyi,
talimata uymayı, kod sorularını, takip sorularını ve hafızayı ölçer.
