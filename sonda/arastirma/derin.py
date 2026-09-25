"""Derin araştırma modu: alt sorular, eksik bilgi turu ve rapor."""
import ollama

from .. import hafiza
from ..ortak import SECENEKLER, bugun, json_sor
from ..web import alan_adi, sayfalari_oku, web_ara
from .araclar import arama_olayi
from .hizli import gecmisi_hazirla
from .kaynaklar import Kaynaklar
from .promptlar import EKSIK_PROMPTU, PLAN_PROMPTU, RAPOR_PROMPTU


def _alt_sorulari_arastir(liste, kaynaklar, okunan, bulgular):
    for p in liste:
        sorgular = [s for s in (p.get("sorgu"), p.get("sorgu_en")) if isinstance(s, str) and s.strip()]
        if not sorgular:
            continue
        haber = bool(p.get("haber"))
        alt_soru = p.get("soru") or sorgular[0]
        sonuclar = web_ara(sorgular, soru=alt_soru, adet=8, haber=haber)
        yield arama_olayi(sorgular, haber, len(sonuclar))

        yeni = [r["url"] for r in sonuclar if r["url"] not in okunan][:5]
        okunan.update(yeni)
        if yeni:
            yield {"tur": "adim", "tip": "oku", "metin": ", ".join(alan_adi(u) for u in yeni)}
        sayfalar = {s["url"]: s for s in sayfalari_oku(yeni, alt_soru, adet=3)}
        for r in sonuclar[:6]:
            sayfa = sayfalar.get(r["url"], {})
            parcalar = sayfa.get("parcalar") or [r["ozet"]]
            if not any(len(x) > 40 for x in parcalar):
                continue
            no, olay = kaynaklar.ekle(r["url"], r["baslik"])
            if olay:
                yield olay
            bulgular.append({"no": no, "baslik": r["baslik"], "alt_soru": alt_soru,
                             "metin": "\n...\n".join(parcalar), "tam": bool(sayfa.get("parcalar"))})


def derin(soru, gecmis, model, onceki_kaynaklar=(), diger_sohbetler=()):
    kaynaklar, okunan, bulgular = Kaynaklar(onceki_kaynaklar), set(), []
    gecmis = gecmisi_hazirla(gecmis, onceki_kaynaklar)
    baglam = "\n".join(f"{m['role']}: {m['content'][:400]}" for m in gecmis[-4:])
    istek = f"Önceki konuşma:\n{baglam}\n\nAraştırma sorusu: {soru}" if baglam else soru

    yield {"tur": "adim", "tip": "plan", "metin": "Araştırma planı hazırlanıyor"}
    plan = json_sor(model, PLAN_PROMPTU.format(tarih=bugun()), istek).get("alt_sorular", [])
    plan = [p for p in plan if isinstance(p, dict) and p.get("sorgu")][:5] or [{"soru": soru, "sorgu": soru}]
    yield {"tur": "adim", "tip": "plan", "metin": f"{len(plan)} alt soru",
           "detay": [p.get("soru", p["sorgu"]) for p in plan]}
    yield from _alt_sorulari_arastir(plan, kaynaklar, okunan, bulgular)

    # İkinci tur: eksik kalan noktaları bul ve ek arama yap
    ozet = "\n".join(f"- {b['alt_soru']}: {b['baslik']}" for b in bulgular)[:6000]
    eksikler = json_sor(model, EKSIK_PROMPTU.format(tarih=bugun(), soru=soru, ozet=ozet)).get("eksikler", [])
    eksikler = [e for e in eksikler if isinstance(e, dict) and e.get("sorgu")][:3]
    if eksikler:
        yield {"tur": "adim", "tip": "plan", "metin": f"Eksik bilgi turu: {len(eksikler)} ek soru",
               "detay": [e.get("soru", e["sorgu"]) for e in eksikler]}
        yield from _alt_sorulari_arastir(eksikler, kaynaklar, okunan, bulgular)

    # Tam okunan sayfalar önce, sonra sadece özeti olanlar
    bulgular.sort(key=lambda b: not b["tam"])
    metin = "\n\n".join(f"[{b['no']}] {b['baslik']} (konu: {b['alt_soru']})\n{b['metin']}" for b in bulgular)
    yield {"tur": "adim", "tip": "yaz", "metin": f"{len(kaynaklar.liste)} kaynaktan rapor yazılıyor"}
    hafiza_metni = hafiza.istem_metni()
    sistem = RAPOR_PROMPTU.format(tarih=bugun(), bulgular=metin[:60000],
                                  hafiza=f"\n{hafiza_metni}\n" if hafiza_metni else "")
    akis = ollama.chat(model=model, stream=True, think=False, options=SECENEKLER,
                       messages=[{"role": "system", "content": sistem}, *gecmis[-4:],
                                 {"role": "user", "content": soru}])
    rapor = ""
    for parca in akis:
        if parca.message.content:
            rapor += parca.message.content
            yield {"tur": "token", "metin": parca.message.content}
    yield {"tur": "cevap_bitti", "metin": rapor}
