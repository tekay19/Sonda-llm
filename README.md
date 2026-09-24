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

| Dosya | Görevi |
|---|---|
| `agent.py` | Ajan orkestrasyonu: arama kararı, araç döngüsü, derin araştırma, takip soruları |
| `webtools.py` | Çok motorlu arama, yeniden sıralama, paralel sayfa ve PDF okuma |
| `hesap.py` | Güvenli hesap makinesi ve tarih hesaplama |
| `hafiza.py` | Sohbetler arası kalıcı hafıza (`veri/hafiza.json`) |
| `server.py` | FastAPI sunucusu ve akış (SSE) uç noktaları |
| `static/index.html` | Arayüz |
| `tests/` | 50 soruluk zorlu test seti ve çalıştırıcı |

## Test

```bash
.venv\Scripts\python tests\calistir.py <etiket>            # tüm testler
.venv\Scripts\python tests\calistir.py <etiket> 3,17,46    # seçili testler
.venv\Scripts\python tests\calistir.py <etiket> --devam    # durdurulan testi sürdür
```

Test seti tuzak soruları, kesin hesabı, tarih hesabını, yanlış öncülleri, güncel bilgiyi,
talimata uymayı, kod sorularını, takip sorularını ve hafızayı ölçer.
