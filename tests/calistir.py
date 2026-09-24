"""Test setini çalıştırır ve puanlar.

Kullanım:  python tests/calistir.py [etiket] [id,id,...]
Sonuçlar tests/sonuc_<etiket>.json dosyasına yazılır.
"""
import json
import re
import sys
import time
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(KOK / "tests"))

import hafiza  # noqa: E402
from agent import calistir  # noqa: E402
from sorular import TESTLER  # noqa: E402

MODEL = "qwen3.6:35b-a3b"


def sor(soru, gecmis, onceki_kaynaklar):
    cevap, kaynaklar, adimlar, hata = "", [], [], None
    basla = time.time()
    for o in calistir(soru, gecmis, MODEL, "hizli", onceki_kaynaklar, oneri=False):
        if o["tur"] == "token":
            cevap += o["metin"]
        elif o["tur"] == "sifirla":
            cevap = ""
        elif o["tur"] == "kaynak":
            kaynaklar.append({k: o[k] for k in ("no", "url", "baslik")})
        elif o["tur"] == "adim":
            adimlar.append(f"{o['tip']}: {o['metin'][:120]}")
        elif o["tur"] == "hata":
            hata = o["metin"]
    return cevap, kaynaklar, adimlar, hata, round(time.time() - basla, 1)


def puanla(test, cevap):
    sorunlar = []
    for desen in test.get("hepsi", []):
        if not re.search(desen, cevap, re.IGNORECASE | re.MULTILINE):
            sorunlar.append(f"eksik: {desen}")
    for desen in test.get("yasak", []):
        if re.search(desen, cevap, re.IGNORECASE | re.MULTILINE):
            sorunlar.append(f"yasak: {desen}")
    if "madde_sayisi" in test:
        maddeler = [s for s in cevap.splitlines() if re.match(r"\s*([-*•]|\d+[.)])\s+", s)]
        if len(maddeler) != test["madde_sayisi"]:
            sorunlar.append(f"{len(maddeler)} madde var, {test['madde_sayisi']} olmalı")
        for m in maddeler:
            kelime = len(re.sub(r"^\s*([-*•]|\d+[.)])\s+|\*\*", "", m).split())
            if kelime > test["maks_kelime"]:
                sorunlar.append(f"madde {kelime} kelime: {m.strip()[:50]}")
        if len([s for s in cevap.splitlines() if s.strip()]) != len(maddeler):
            sorunlar.append("maddeler dışında metin var")
    return sorunlar


def main():
    argumanlar = [a for a in sys.argv[1:] if not a.startswith("--")]
    etiket = argumanlar[0] if argumanlar else "1"
    secilen = {int(x) for x in argumanlar[1].split(",")} if len(argumanlar) > 1 else None
    devam = "--devam" in sys.argv
    testler = [t for t in TESTLER if not secilen or t["id"] in secilen]
    cikti = KOK / "tests" / f"sonuc_{etiket}.json"
    sonuclar = []
    if devam and cikti.exists():  # durdurulan testi kaldığı yerden sürdür
        sonuclar = json.loads(cikti.read_text(encoding="utf-8"))
        bitenler = {s["id"] for s in sonuclar}
        testler = [t for t in testler if t["id"] not in bitenler]
        print(f"Devam: {len(bitenler)} test tamamlanmış, {len(testler)} kaldı", flush=True)
    elif not secilen or 49 in secilen:
        hafiza.sil()  # hafıza testinin temiz başlaması için
    for t in testler:
        if t.get("bekle"):
            time.sleep(t["bekle"])  # arka plandaki hafıza güncellemesi bitsin
        gecmis, onceki = [], []
        for soru in t["turlar"]:
            cevap, kaynaklar, adimlar, hata, sure = sor(soru, gecmis, onceki)
            gecmis += [{"role": "user", "content": soru}, {"role": "assistant", "content": cevap}]
            onceki = kaynaklar or onceki
        sorunlar = puanla(t, cevap) + ([f"HATA: {hata}"] if hata else [])
        durum = "GECTI" if not sorunlar else "KALDI"
        if t.get("manuel") and not sorunlar:
            durum = "MANUEL"
        sonuclar.append({"id": t["id"], "kat": t["kat"], "soru": t["turlar"][-1], "durum": durum,
                         "sorunlar": sorunlar, "sure": sure, "kaynak": len(kaynaklar),
                         "adimlar": adimlar, "cevap": cevap})
        print(f"[{t['id']:2}] {durum:6} {sure:6.1f}s  {t['kat']:8} {t['turlar'][-1][:60]}"
              + (f"  -> {sorunlar}" if sorunlar else ""), flush=True)
        cikti.write_text(json.dumps(sonuclar, ensure_ascii=False, indent=2), encoding="utf-8")

    gecen = sum(s["durum"] == "GECTI" for s in sonuclar)
    manuel = sum(s["durum"] == "MANUEL" for s in sonuclar)
    print(f"\nSONUÇ: {gecen} geçti, {manuel} manuel inceleme, "
          f"{len(sonuclar) - gecen - manuel} kaldı / {len(sonuclar)}", flush=True)


if __name__ == "__main__":
    main()
