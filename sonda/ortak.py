"""Modül genelinde ortak: model ayarları, bugünün tarihi, JSON cevaplı model çağrısı."""
import json
from datetime import date

import ollama


AYLAR = "Ocak Şubat Mart Nisan Mayıs Haziran Temmuz Ağustos Eylül Ekim Kasım Aralık".split()


GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


# Tüm çağrılarda aynı bağlam boyutu: değişirse Ollama modeli baştan yükler
SECENEKLER = {"num_ctx": 32768, "temperature": 0.3}


JSON_SECENEKLERI = {**SECENEKLER, "temperature": 0}


def bugun():
    g = date.today()
    return f"{g.day} {AYLAR[g.month - 1]} {g.year} {GUNLER[g.weekday()]}"


def json_sor(model, sistem, kullanici=None):
    mesajlar = [{"role": "system", "content": sistem}]
    if kullanici:
        mesajlar.append({"role": "user", "content": kullanici})
    yanit = ollama.chat(model=model, format="json", think=False, options=JSON_SECENEKLERI, messages=mesajlar)
    try:
        veri = json.loads(yanit.message.content)
        return veri if isinstance(veri, dict) else {}
    except json.JSONDecodeError:
        return {}
