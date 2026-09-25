"""Numaralı kaynak listesi (cevaptaki [1], [2] atıfları)."""
import re

from ..web import alan_adi


class Kaynaklar:
    """Numaralı kaynak listesi. Takip sorularında önceki cevabın kaynakları aynı numarayla korunur."""

    def __init__(self, onceki=()):
        self.liste, self._no = [], {}
        self.onceki = {int(k["no"]): k for k in onceki if k.get("url")}
        for k in self.onceki.values():
            self._no[k["url"]] = int(k["no"])
        self._sonraki = max(self.onceki, default=0) + 1

    def ekle(self, url, baslik):
        """Kaynağın numarasını döner; bu cevapta yeniyse ayrıca olay da döner."""
        if url in self._no:
            no = self._no[url]
            if no in self.onceki and not any(k["no"] == no for k in self.liste):
                return no, self._kaydet(no, url, self.onceki[no].get("baslik", baslik))
            return no, None
        no = self._sonraki
        self._sonraki += 1
        self._no[url] = no
        return no, self._kaydet(no, url, baslik)

    def _kaydet(self, no, url, baslik):
        kayit = {"no": no, "url": url, "baslik": baslik, "alan": alan_adi(url)}
        self.liste.append(kayit)
        return {"tur": "kaynak", **kayit}

    def atiflari_ekle(self, metin):
        """Cevapta atıf yapılan önceki kaynakları bu cevabın listesine ekler."""
        for n in sorted({int(x) for x in re.findall(r"\[(\d{1,3})\]", metin)}):
            if n in self.onceki and not any(k["no"] == n for k in self.liste):
                yield self._kaydet(n, self.onceki[n]["url"], self.onceki[n].get("baslik", ""))
