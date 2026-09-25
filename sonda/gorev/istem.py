"""Her adımda modele giden istemin kurulması (plan, notlar, hafıza, son adımlar, sayfa)."""
from ..web import alan_adi
from . import ayar
from .sayfa import sayfa_ozeti


def istem(gorev_metni, onceki, derinlik, notlar, hafiza_, adimlar, sayfa, geri_bildirim, adim_no, maks):
    p = [f"GÖREV: {gorev_metni}"]
    if onceki:
        p.append(f"ÖNCEKİ KONUŞMA (bağlam):\n{onceki}")
    plan = "\n".join(f"{i}. {a}" for i, a in enumerate(derinlik["plan"], 1)) or "(plan yok)"
    p.append(f"PLANIN ({derinlik['derinlik']} görev, en az {derinlik['min_site']} farklı siteden bilgi topla):\n{plan}")
    p.append(f"ADIM: {adim_no}/{maks}")
    p.append("NOTLARIN:\n" + ("\n".join(f"- {n['metin']} ({alan_adi(n['url'])})" for n in notlar) or "(henüz yok)"))
    p.append("ZİYARET EDİLEN SAYFALAR (görev boyunca hafızan):\n" + hafiza_.metin())
    p.append("SON ADIMLAR:\n" + ("\n".join(adimlar[-ayar.GECMIS_ADIM:]) or "(ilk adım)"))
    if geri_bildirim:
        p.append(f"SON EYLEMİN SONUCU: {geri_bildirim}")
    p.append(sayfa_ozeti(sayfa))
    p.append("Sıradaki TEK eylemi JSON olarak ver.")
    return "\n\n".join(p)
