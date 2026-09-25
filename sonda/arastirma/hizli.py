"""Hızlı mod: arama kararı, en iyi sayfaları okuma ve araç döngüsü."""
import ollama

from ..ortak import SECENEKLER, bugun, json_sor
from .araclar import ARACLAR, arac_calistir
from .kaynaklar import Kaynaklar
from .promptlar import ARAMA_CALISMIYOR, ON_KARAR_PROMPTU, sistem_promptu


MAKS_ARAC_TURU = 10


def gecmisi_hazirla(gecmis, onceki_kaynaklar):
    """Uzun mesajları kısaltır; son cevabın kaynak listesini modele görünür yapar."""
    hazir = [{"role": m["role"], "content": m["content"][:4000]} for m in gecmis[-10:]]
    if onceki_kaynaklar and hazir and hazir[-1]["role"] == "assistant":
        liste = "\n".join(f"[{k['no']}] {k.get('baslik', '')} ({k['url']})" for k in onceki_kaynaklar[:30])
        hazir[-1]["content"] += f"\n\n(Bu cevabın kaynakları:\n{liste})"
    return hazir


def hizli(soru, gecmis, model, onceki_kaynaklar=(), diger_sohbetler=()):
    kaynaklar = Kaynaklar(onceki_kaynaklar)
    gecmis = gecmisi_hazirla(gecmis, onceki_kaynaklar)
    mesajlar = [{"role": "system", "content": sistem_promptu(diger_sohbetler)}, *gecmis,
                {"role": "user", "content": soru}]

    # 1) Arama kararını modele bırakmadan orkestratör verir: model eski bilgisiyle cevaplamasın
    son = "\n".join(f"{m['role']}: {m['content'][:400]}" for m in gecmis[-4:])
    karar = json_sor(model, ON_KARAR_PROMPTU.format(tarih=bugun()),
                      f"Önceki konuşma:\n{son or '(yok)'}\n\nSon mesaj: {soru}")
    dusunme = bool(karar.get("zor"))
    if karar.get("arama", True):
        sorgular = [q for q in karar.get("sorgular", []) if isinstance(q, str) and q.strip()][:3] or [soru]
        arg = {"sorgular": sorgular, "haber": bool(karar.get("haber"))}
        arama_sonucu, olaylar = arac_calistir("web_ara", arg, soru, kaynaklar)
        yield from olaylar
        # En iyi sonuçları doğrudan oku: özetler çoğu zaman ayrıntı için yetersiz
        en_iyiler = [k["url"] for k in kaynaklar.liste[:4]]
        if not en_iyiler:
            # Model, boş aramada uyarılara rağmen eski bilgisiyle cevap uyduruyor ("henüz oynanmadı" gibi).
            # web_ara zaten yeniden denedi; sonuç yoksa model çağrılmadan dürüstçe söylenir.
            yield {"tur": "token", "metin": ARAMA_CALISMIYOR}
            yield {"tur": "cevap_bitti", "metin": ARAMA_CALISMIYOR}
            return
        okuma_sonucu, olaylar = arac_calistir("sayfa_oku", {"urller": en_iyiler}, soru, kaynaklar)
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
            sonuc, olaylar = arac_calistir(c.function.name, dict(c.function.arguments), soru, kaynaklar)
            yield from olaylar
            mesajlar.append({"role": "tool", "content": sonuc[:16000], "tool_name": c.function.name})
