"""Kesin hesap araçları: güvenli matematik ve tarih hesaplama (dil modelleri burada sık hata yapar)."""
import ast
import math
import operator
from datetime import date, datetime, timedelta

GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

_OPERATORLER = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow,
    ast.USub: operator.neg, ast.UAdd: operator.pos,
}
_FONKSIYONLAR = {
    "sqrt": math.sqrt, "log": math.log, "log10": math.log10, "log2": math.log2, "exp": math.exp,
    "sin": math.sin, "cos": math.cos, "tan": math.tan, "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "floor": math.floor, "ceil": math.ceil, "round": round, "abs": abs, "min": min, "max": max,
    "factorial": math.factorial, "comb": math.comb, "perm": math.perm, "gcd": math.gcd, "lcm": math.lcm,
    "radians": math.radians, "degrees": math.degrees, "sum": sum,
}
_SABITLER = {"pi": math.pi, "e": math.e}


def _degerlendir(dugum):
    if isinstance(dugum, ast.Expression):
        return _degerlendir(dugum.body)
    if isinstance(dugum, ast.Constant) and isinstance(dugum.value, (int, float)):
        return dugum.value
    if isinstance(dugum, ast.Name) and dugum.id in _SABITLER:
        return _SABITLER[dugum.id]
    if isinstance(dugum, ast.BinOp) and type(dugum.op) in _OPERATORLER:
        sol, sag = _degerlendir(dugum.left), _degerlendir(dugum.right)
        if isinstance(dugum.op, ast.Pow) and abs(sag) > 1000:
            raise ValueError("üs çok büyük")
        return _OPERATORLER[type(dugum.op)](sol, sag)
    if isinstance(dugum, ast.UnaryOp) and type(dugum.op) in _OPERATORLER:
        return _OPERATORLER[type(dugum.op)](_degerlendir(dugum.operand))
    if isinstance(dugum, ast.Call) and isinstance(dugum.func, ast.Name) and dugum.func.id in _FONKSIYONLAR:
        return _FONKSIYONLAR[dugum.func.id](*[_degerlendir(a) for a in dugum.args])
    if isinstance(dugum, (ast.List, ast.Tuple)):
        return [_degerlendir(e) for e in dugum.elts]
    raise ValueError(f"desteklenmeyen ifade: {ast.dump(dugum)[:60]}")


def hesapla(ifade):
    ifade = ifade.replace("^", "**").replace("×", "*").replace("÷", "/")
    if "(" not in ifade:  # fonksiyon argümanı yoksa virgül ondalık ayracıdır (Türkçe yazım: 1,5)
        ifade = ifade.replace(",", ".")
    try:
        sonuc = _degerlendir(ast.parse(ifade, mode="eval"))
    except Exception as e:
        return f"Hesaplanamadı ({e}). Python sözdizimi kullan, ör: (1250*0.18)+sqrt(16)"
    if isinstance(sonuc, float):
        sonuc = round(sonuc, 10)
        if sonuc.is_integer():
            sonuc = int(sonuc)
    return f"{ifade} = {sonuc}"


def _tarih_oku(metin):
    metin = (metin or "").strip().lower()
    if metin in ("", "bugün", "bugun", "today"):
        return date.today()
    for bicim in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(metin, bicim).date()
        except ValueError:
            pass
    raise ValueError(f"tarih anlaşılamadı: {metin} (YYYY-AA-GG veya GG.AA.YYYY kullan)")


def _yaz(t):
    return f"{t.strftime('%d.%m.%Y')} {GUNLER[t.weekday()]}"


def tarih_hesapla(baslangic="bugün", gun=0, hafta=0, bitis=None):
    """Tarihe gün/hafta ekler veya iki tarih arasındaki farkı bulur; haftanın gününü de verir."""
    try:
        bas = _tarih_oku(baslangic)
        if bitis:
            bit = _tarih_oku(bitis)
            fark = (bit - bas).days
            return f"{_yaz(bas)} ile {_yaz(bit)} arası {fark} gün ({fark // 7} hafta {fark % 7} gün)."
        sonuc = bas + timedelta(days=int(gun) + 7 * int(hafta))
        return f"{_yaz(bas)} + {int(gun)} gün + {int(hafta)} hafta = {_yaz(sonuc)}"
    except Exception as e:
        return f"Tarih hesaplanamadı: {e}"
