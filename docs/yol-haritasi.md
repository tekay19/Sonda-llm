# Sonda — Yol Haritası ve Açık Kararlar

*Son güncelleme: 25 Eylül 2026*

## 0. Gemini sağlayıcı (25 Eylül akşamı)

Sonda artık yerel modellerin yanında Gemini ile de çalışıyor (`gemini-saglayici` dalı). Ayarlar'dan anahtar eklenince
seçicide iki ucuz model çıkıyor: Gemini Flash-Lite (en ucuz) ve Gemini Flash. Pro, pahalı olduğu için listelenmiyor.

- Yerel sahte mağazadaki SSD görevi: Flash-Lite ile 11 sn, Flash ile 15 sn. Hızlı araştırma yaklaşık 20 sn sürüyor.
- Görevde verilen şifre hiçbir modele gitmiyor, model `{SIFRE_1}` görüyor.
- Gerçek API testleri: `.venv\Scripts\python -m pytest -m gemini`.

**Açık iş:** Upwork inceleme görevini Gemini ile çalıştırıp yerel modeldeki 22 dakikalık çalışmayla karşılaştırmak
(kullanıcının Chrome'u ve hesabıyla, kullanıcı hazır olduğunda).

## 1. Bugün yapılanlar

**Test sonucu (50 soru):** 40 geçti, 9 elle kontrol edildi, 1 kaldı. Elle kontrolde 1 hata daha çıktı, yani toplam **2 gerçek hata**.

| Hata | Neden | Düzeltme |
|---|---|---|
| 23: "1 Ocak 2027'ye kaç gün kaldı?" (98 yerine 99 olmalıydı) | Tarih aracı yerine webdeki, başka bir günde hesaplanmış sayıyı aldı | Tarih/gün hesabı soruları artık web aramasına gitmiyor, tarih aracıyla hesaplanıyor (`agent.py`, ön karar promptu) |
| 32: "2026 Dünya Kupası'nı kim kazandı?" ("henüz oynanmadı" dedi) | Arama motorları geçici olarak boş döndü; model eski bilgisiyle cevap uydurdu | Boş arama yeniden deneniyor, haber araması boşsa normal aramaya geçiliyor (`webtools.py`). Yine boşsa model çağrılmıyor, dürüst bir "sonuç alamadım" mesajı gösteriliyor (`agent.py`) |

Ek düzeltmeler:
- Kaynak yokken modelin uydurduğu `[1]` atıfları arayüzde gösterilmiyor (`static/index.html`).
- Tarih testlerinin beklenen cevapları artık test günü hesaplanıyor (`tests/sorular.py`).

**Doğrulama:** Etkilenen 13 test yeniden çalıştırıldı, hepsi doğru. Tarih soruları 25-112 sn yerine 5-25 sn sürüyor.

**Bekleyenler:**
- [ ] Değişiklikler henüz commit'lenmedi.
- [ ] Hafıza testleri (49-50) gerçek `veri/hafiza.json` dosyasını siliyor ve oraya test bilgisi ("Deniz, İzmir") yazıyor. Testin ayrı bir hafıza dosyası kullanması gerekiyor.
- [ ] Ollama güncellemesi yarım kaldı (kurulu sürüm 0.34.4 çalışıyor).

---

## 2. Sonda nasıl farklılaşır?

Perplexity veya ChatGPT'nin kopyası olmak yerine, Sonda'nın onlarda olmayan üç gücüne yaslanmak:

1. **Senin bilgisayarında çalışıyor:** dosyalarına gizlilik sorunu olmadan erişebilir.
2. **Zamanı bedava:** bulut şirketleri araştırmayı maliyet yüzünden 1-2 dakikayla sınırlar. Sonda saatlerce araştırabilir.
3. **Türkçe odaklı:** Türk ve yabancı kaynakları birlikte tarayabilir.

**Konum:** *"Senin için çalışan, yorulmayan, özel araştırmacı."* Hızlı sohbet aracı değil, iş teslim eden araştırmacı.

| # | Özellik | Kısaca |
|---|---|---|
| 1 | 🌙 Gece Araştırması | Akşam konuyu verirsin, sabah grafikli ve kaynaklı uzun bir rapor bulursun |
| 2 | 🗂️ Senin dosyaların ve web bir arada | **← SEÇİLDİ.** Ayrıntılar aşağıda |
| 3 | 🌍 İki bakış açısı | "Türk basını ne diyor, dünya basını ne diyor": ortak noktalar ve farklar |
| 4 | 🧠 Büyüyen bilgi arşivi | Her araştırma bağlantılı bir arşive kaydedilir; "geçen ay ne bulmuştuk, ne değişti?" |
| 5 | ✅ Kanıt Modu | Cevaptaki her cümle kaynaktaki birebir alıntıya bağlanır, çelişkiler gösterilir |
| 6 | 🎬 Canlı araştırma sahnesi | Arama sırasında siteler kart kart belirir, okuma ilerlemesi izlenir |
| 7 | 📊 Görsel cevaplar | Soruya göre otomatik grafik, karşılaştırma tablosu ya da zaman çizelgesi |
| 8 | 🔔 Konu takibi | Bir konuyu her gün arka planda yeniden araştırır, değişiklik olursa haber verir |

Önerilen sıra: **Dosyalar ve web (2)**, sonra **Kanıt Modu (5)**, sonra **Gece Araştırması (1)**.

---

## 3. Seçilen özellik: Senin dosyaların ve web bir arada

**Örnek:** *"Şu sözleşmemdeki kira artış maddesi yeni yasaya uygun mu?"* Sonda PDF'i okur, güncel yasayı webde bulur, ikisini karşılaştırır. Belge hiçbir sunucuya gitmez.

**Anlaşılan:**
- Kullanıcı kendi belgesini verir. Sonda belgeyi okur, ilgili güncel bilgiyi webde bulur ve karşılaştırır.
- *Varsayım (onay bekliyor):* Cevapta hangi bilginin belgeden, hangisinin webden geldiği açıkça ayrılır. Örneğin 📄 "Sözleşme, madde 4" ve 🌐 "resmigazete.gov.tr".

**Hazır olan altyapı:** PDF okuma (`pypdf`), metni parçalara bölme ve anlamsal arama (`bge-m3`, `webtools.py`). Web sayfaları için kullanılan parçalar belgeler için de kullanılabilir.

### Açık soru 1 (sıradaki karar): Belgeler Sonda'ya nasıl gelsin?

- **A) Sohbete ekleme:** Dosyayı sürükle-bırak ya da ataç simgesiyle sohbete eklersin; dosya o sohbete ait olur. Basit ve tanıdık.
- **B) Belge kütüphanesi:** "Belgelerim" klasörünü bir kez gösterirsin; Sonda tüm dosyaları arka planda dizinler ve hangi sohbette olursan ol ilgili belgeyi kendisi bulur. Daha güçlü, daha büyük bir iş.
- **C) İkisi birden (önerilen):** Önce A teslim edilir, B arkasından eklenir.

### Sonra konuşulacak sorular
- Hangi dosya türleri? (PDF, Word, Excel, görsel/tarama → OCR?)
- Taranmış PDF'ler (metni olmayan, resim olan) desteklensin mi?
- Karşılaştırma cevabının biçimi: düz metin mi, "uygun / uygun değil / belirsiz" tablosu mu?
- Belgeler nerede saklansın, nasıl silinsin?

**Süreç:** Sorular netleşince kısa bir tasarım belgesi yazılacak ve onayından sonra kodlamaya geçilecek.

---

## 4. Ertelenen proje: UI tasarımında uzman kodlama ajanı

İndirilebilir bir masaüstü uygulaması. Uzun (gerekirse 10 saat) otonom döngüyle etkileyici web siteleri yazar.

- **Karar verildi:** Model olarak **Gemini API ve yerel Ollama birlikte**, çıktı olarak **Next.js** (App Router ve Tailwind).
- **Açık soru:** Otonomi düzeyi. Seçenekler: tamamen otonom, tasarım yönü onaylandıktan sonra otonom (önerilen), ya da her adımda etkileşimli.
