"""Görev hata ayıklama kaydı: her adımda modelin gördüğü istem ve verdiği karar veri/gorev_kayitlari/ altına
JSON satırları olarak yazılır (şifreler gizlenir). "Sonda neden böyle yaptı?" sorusunun cevabı buradadır."""
import json
import time
from pathlib import Path

from . import ayar


class GorevKaydi:
    def __init__(self, gorev_id, gizliler):
        self.gizliler = gizliler  # canlı küme: görev sırasında eklenen şifreler de gizlenir
        klasor = Path(ayar.KAYIT_KLASORU)
        self.dosya = klasor / f"{time.strftime('%Y%m%d-%H%M%S')}_{gorev_id}.jsonl"
        try:
            klasor.mkdir(parents=True, exist_ok=True)
            eskiler = sorted(klasor.glob("*.jsonl"))
            for f in eskiler[:max(0, len(eskiler) - ayar.KAYIT_SAYISI + 1)]:
                f.unlink(missing_ok=True)
        except OSError:
            pass

    def yaz(self, kayit):
        metin = json.dumps(kayit, ensure_ascii=False)
        for gizli in self.gizliler:
            if len(gizli) >= 4:
                metin = metin.replace(gizli, "•••")
        try:
            with open(self.dosya, "a", encoding="utf-8") as f:
                f.write(metin + "\n")
        except OSError:
            pass  # kayıt yazılamazsa görev yine sürer
