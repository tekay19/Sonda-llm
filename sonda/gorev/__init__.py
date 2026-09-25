"""Görev modu: Sonda kullanıcının Chrome'unda, onun adına görev yapar.

Akış: görevin derinliğini belirle ve planla -> sayfaya bak -> modele sor (tek eylem, JSON) -> koruma.py'den
geçir -> uygula. Engellenen adımlar ve 2FA kullanıcıya devredilir.

  ayar      sınırlar ve süreler          promptlar  model istemleri
  sayfa     sayfa özeti, 2FA, hafıza     karar      derinlik/plan ve eylem kararı
  istem     adım istemi                  eylemler   eylemlerin uygulanması
  dongu     görev döngüsü                yonetim    iş parçacığı, komutlar, olay akışı
"""
from . import ayar, dongu, eylemler, istem, karar, promptlar, sayfa
from .sayfa import iki_adim_mi, sayfa_ozeti
from .yonetim import GOREVLER, calistir, komut_ver, tarayici_isinde

__all__ = ["GOREVLER", "ayar", "calistir", "dongu", "eylemler", "iki_adim_mi", "istem", "karar", "komut_ver",
           "promptlar", "sayfa", "sayfa_ozeti", "tarayici_isinde"]
