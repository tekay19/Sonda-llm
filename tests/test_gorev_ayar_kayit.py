"""Final inceleme Minor 1: testler gerçek görev kayıt klasörüne yazmamalı (kullanıcının kayıtlarını siler)."""
from sonda import gorev


def test_testlerde_kayit_klasoru_gecici(tmp_path_factory):
    assert "veri" not in str(gorev.ayar.KAYIT_KLASORU).replace("\\", "/").split("/")[-2:]
    assert "pytest" in str(gorev.ayar.KAYIT_KLASORU).lower() or "tmp" in str(gorev.ayar.KAYIT_KLASORU).lower()
