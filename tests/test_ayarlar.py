"""API anahtarının saklanması."""
import pytest

from sonda import ayarlar


@pytest.fixture(autouse=True)
def gecici_dosya(tmp_path, monkeypatch):
    monkeypatch.setattr(ayarlar, "DOSYA", tmp_path / "veri" / "ayarlar.json")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


def test_anahtar_yoksa_none():
    assert ayarlar.gemini_anahtari() is None


def test_kaydet_oku_sil():
    ayarlar.gemini_kaydet("  AIzaKAYITLI  ")
    assert ayarlar.gemini_anahtari() == "AIzaKAYITLI"
    ayarlar.gemini_sil()
    assert ayarlar.gemini_anahtari() is None


def test_ortam_degiskeni_yedek_kayitli_oncelikli(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "ORTAM")
    assert ayarlar.gemini_anahtari() == "ORTAM"
    ayarlar.gemini_kaydet("KAYITLI")
    assert ayarlar.gemini_anahtari() == "KAYITLI"


def test_bozuk_dosya_bos_sayilir():
    ayarlar.DOSYA.parent.mkdir(parents=True)
    ayarlar.DOSYA.write_text("{bozuk", encoding="utf-8")
    assert ayarlar.gemini_anahtari() is None
    ayarlar.gemini_kaydet("K")
    assert ayarlar.gemini_anahtari() == "K"


def test_anahtar_dosyasi_yalnizca_sahibine_acik(monkeypatch):
    modlar = []
    monkeypatch.setattr(ayarlar.os, "chmod", lambda yol, mod: modlar.append((str(yol), mod)))
    ayarlar.gemini_kaydet("K")
    assert modlar == [(str(ayarlar.DOSYA), 0o600)]
