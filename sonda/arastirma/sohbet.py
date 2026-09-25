"""Sohbet: web araması yapmadan, önceki konuşmaya ve kaynaklarına dayanarak cevap."""
from .. import model as saglayici

from ..ortak import SECENEKLER
from .hizli import gecmisi_hazirla
from .kaynaklar import Kaynaklar
from .promptlar import sistem_promptu


def sohbet(soru, gecmis, model, onceki_kaynaklar=(), diger_sohbetler=()):
    kaynaklar = Kaynaklar(onceki_kaynaklar)
    mesajlar = [{"role": "system", "content": sistem_promptu(diger_sohbetler)},
                *gecmisi_hazirla(gecmis, onceki_kaynaklar), {"role": "user", "content": soru}]
    cevap = ""
    for parca in saglayici.sohbet(model, mesajlar, akis=True, secenekler=SECENEKLER):
        if parca.metin:
            cevap += parca.metin
            yield {"tur": "token", "metin": parca.metin}
    yield from kaynaklar.atiflari_ekle(cevap)
    yield {"tur": "cevap_bitti", "metin": cevap}
