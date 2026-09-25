"""Gerçek web görevlerini kullanıcının Chrome'unda çalıştırır.
Kullanım: python tests/gorev_calistir.py [etiket] [id,id,...]
Sonuçlar tests/gorev_sonuc_<etiket>.json dosyasına yazılır. Devretmelerde otomatik 'durdur' verilir."""
import json
import sys
import time
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(KOK / "tests"))

from sonda import gorev  # noqa: E402
from gorevler import GOREVLER  # noqa: E402

MODEL = "qwen3.6:35b-a3b"


def main():
    etiket = sys.argv[1] if len(sys.argv) > 1 else "1"
    secili = {int(x) for x in sys.argv[2].split(",")} if len(sys.argv) > 2 else None
    sonuclar = []
    for g in GOREVLER:
        if secili and g["id"] not in secili:
            continue
        basla, adimlar, cevap, devir = time.time(), [], "", []
        for o in gorev.calistir(g["gorev"], MODEL):
            if o["tur"] == "adim":
                adimlar.append(f"{o['tip']}: {o['metin']}")
                print(f"  [{g['id']}] {o['tip']}: {o['metin'][:100]}", flush=True)
            elif o["tur"] == "kullaniciya":
                devir.append(o["sebep"])
                gorev.komut_ver(o["id"], "durdur")
            elif o["tur"] == "token":
                cevap += o["metin"]
        sonuclar.append({**g, "sure": round(time.time() - basla, 1), "adim_sayisi": len(adimlar),
                         "devir": devir, "cevap": cevap, "adimlar": adimlar})
        print(f"#{g['id']} {sonuclar[-1]['sure']} sn, {len(adimlar)} adım\n{cevap[:400]}\n", flush=True)
    (KOK / "tests" / f"gorev_sonuc_{etiket}.json").write_text(json.dumps(sonuclar, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
