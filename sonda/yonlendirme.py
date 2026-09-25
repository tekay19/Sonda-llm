"""Görev modunda gelen mesajın ne olduğuna karar verir: tarayıcı görevi, sohbet ya da hızlı bilgi sorusu.
Böylece "teşekkürler" ya da "tabloyu kısalt" gibi mesajlar tarayıcı açmadan cevaplanır."""
from .model import ModelHatasi
from .ortak import bugun, json_sor

HEDEFLER = ("gorev", "sohbet", "bilgi")

YON_PROMPTU = """Bugün {tarih}. Kullanıcı Sonda'nın "Görev" modunda bir mesaj yazdı. Sonda bu modda kullanıcının
tarayıcısında sitelere girip iş yapabilir. Mesajın ne olduğuna karar ver. Sadece JSON: {{"hedef": "gorev|sohbet|bilgi"}}
- gorev: tarayıcıda sitelere girip gezinmek, aramak, incelemek, karşılaştırmak, form doldurmak, hesapta/profilde
  bir şeye bakmak ya da düzenlemek, sepete eklemek gereken iş. Önceki görevin devamı olan yeni bir tarayıcı işi de
  gorev'dir ("şimdi ikincisini sepete ekle", "aynısını Amazon'da da bak").
- sohbet: selam, teşekkür, onay; önceki cevap hakkında soru, yorum ya da düzenleme isteği ("hangisi daha iyi?",
  "tabloyu kısalt", "neden öyle dedin?"); önceki konuşmadan cevaplanabilecek her şey.
- bilgi: tek bir güncel bilgi ya da kısa bir soru ("dolar kaç?", "yarın İzmir'de hava nasıl?"); siteye girip işlem
  yapmadan web aramasıyla cevaplanabilir.
Emin değilsen: mesaj önceki cevaba dayanıyorsa sohbet, yoksa gorev."""


def yon_belirle(model, soru, gecmis):
    son = "\n".join(f"{m['role']}: {m['content'][:300]}" for m in list(gecmis)[-4:])
    try:
        veri = json_sor(model, YON_PROMPTU.format(tarih=bugun()), f"Önceki konuşma:\n{son or '(yok)'}\n\nSon mesaj: {soru}")
    except ModelHatasi:
        raise  # anahtar/kota sorunu: tarayıcı boşuna açılmasın, kullanıcı hemen görsün
    except Exception:
        return "gorev"
    hedef = veri.get("hedef") if isinstance(veri, dict) else None
    return hedef if hedef in HEDEFLER else "gorev"
