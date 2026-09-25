"""Gemini sağlayıcısı: sahte istemciyle dönüşüm, akış, araçlar, hata çevirisi."""
from types import SimpleNamespace as NS

import httpx
import pytest
from google.genai import errors, types

from sonda import ayarlar, model
from sonda.model import AracCagrisi, ModelHatasi, gemini_saglayici as gs

ANAHTAR = "AIzaSyTESTANAHTAR0123456789abcdefghijklm"


def yanit(*parcalar, bitis="STOP", engel=None):
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=list(parcalar)), finish_reason=bitis)],
        prompt_feedback=types.GenerateContentResponsePromptFeedback(block_reason=engel) if engel else None)


def api_hatasi(kod, mesaj="x"):
    sinif = errors.ClientError if kod < 500 else errors.ServerError
    return sinif(kod, {"error": {"code": kod, "message": mesaj, "status": "S"}})


class SahteModeller:
    def __init__(self, cevaplar):
        self.cevaplar, self.cagrilar = list(cevaplar), []

    def _sonraki(self, k):
        self.cagrilar.append(k)
        c = self.cevaplar.pop(0)
        if isinstance(c, Exception):
            raise c
        return c

    def generate_content(self, **k):
        return self._sonraki(k)

    def generate_content_stream(self, **k):
        return iter(self._sonraki(k))

    def list(self, **k):
        return self._sonraki(k)


@pytest.fixture
def sahte(monkeypatch, tmp_path):
    monkeypatch.setattr(ayarlar, "DOSYA", tmp_path / "ayarlar.json")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    ayarlar.gemini_kaydet(ANAHTAR)
    monkeypatch.setattr(gs, "YENIDEN_DENEME_BEKLEMESI", [0, 0, 0])
    gs._model_onbellegi.clear()

    def kur(*cevaplar):
        m = SahteModeller(cevaplar)
        monkeypatch.setattr(gs, "_istemci", lambda anahtar: NS(models=m))
        return m
    return kur


def test_sistem_rol_ve_gorsel_donusumu(sahte):
    m = sahte(yanit(types.Part(text="tamam")))
    y = gs.sohbet("gemini:gemini-flash-latest", [
        {"role": "system", "content": "SİSTEM"},
        {"role": "user", "content": "soru", "images": [b"\xff\xd8jpeg"]},
        {"role": "assistant", "content": "önceki"},
        {"role": "user", "content": "yeni"}])
    assert y.metin == "tamam"
    k = m.cagrilar[0]
    assert k["model"] == "gemini-flash-latest"
    assert k["config"].system_instruction == "SİSTEM"
    assert [c.role for c in k["contents"]] == ["user", "model", "user"]
    ilk = k["contents"][0].parts
    assert ilk[0].text == "soru" and ilk[1].inline_data.mime_type == "image/jpeg" and ilk[1].inline_data.data == b"\xff\xd8jpeg"


def test_json_modu_ve_sicaklik(sahte):
    m = sahte(yanit(types.Part(text='{"a": 1}')))
    gs.sohbet("gemini:g", [{"role": "user", "content": "x"}], json=True, secenekler={"num_ctx": 32768, "temperature": 0})
    c = m.cagrilar[0]["config"]
    assert c.response_mime_type == "application/json" and c.temperature == 0


def test_dusunme_ayari(sahte):
    m = sahte(yanit(types.Part(text="a")), yanit(types.Part(text="b")))
    gs.sohbet("gemini:g", [{"role": "user", "content": "x"}], dusun=False)
    gs.sohbet("gemini:g", [{"role": "user", "content": "x"}], dusun=True)
    kapali, acik = (c["config"].thinking_config for c in m.cagrilar)
    assert kapali.include_thoughts is not True and kapali.thinking_level == types.ThinkingLevel.LOW
    assert acik.include_thoughts is True and acik.thinking_level == types.ThinkingLevel.HIGH


def test_dusunme_ayarini_desteklemeyen_model_ayarsiz_denenir(sahte):
    m = sahte(api_hatasi(400, "Thinking level is not supported for this model."), yanit(types.Part(text="ok")))
    assert gs.sohbet("gemini:gemini-2.0-flash", [{"role": "user", "content": "x"}]).metin == "ok"
    assert m.cagrilar[1]["config"].thinking_config is None


def test_akis_parcalari(sahte):
    sahte([yanit(types.Part(text="düşünüyorum", thought=True)), yanit(types.Part(text="Mer")),
           yanit(types.Part(text="haba"))])
    p = list(gs.sohbet("gemini:g", [{"role": "user", "content": "x"}], akis=True, dusun=True))
    assert [x.dusunce for x in p] == ["düşünüyorum", "", ""]
    assert "".join(x.metin for x in p) == "Merhaba"


def test_arac_tanimi_ve_cagrisi(sahte):
    from sonda.arastirma.araclar import ARACLAR
    cagri = types.Part(function_call=types.FunctionCall(name="web_ara", args={"sorgular": ["a"]}),
                       thought_signature=b"IMZA")
    m = sahte([yanit(cagri)])
    p = list(gs.sohbet("gemini:g", [{"role": "user", "content": "x"}], akis=True, araclar=ARACLAR))
    assert p[0].arac_cagrilari == [AracCagrisi("web_ara", {"sorgular": ["a"]}, b"IMZA")]
    bildirimler = m.cagrilar[0]["config"].tools[0].function_declarations
    assert [b.name for b in bildirimler] == [a["function"]["name"] for a in ARACLAR]
    assert bildirimler[0].parameters_json_schema == ARACLAR[0]["function"]["parameters"]


def test_arac_cagrisi_ve_cevabi_gidis_donus(sahte):
    m = sahte(yanit(types.Part(text="cevap")))
    gs.sohbet("gemini:g", [
        {"role": "user", "content": "soru"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "web_ara", "arguments": {"sorgular": ["a"]}}, "imza": b"IMZA"},
            {"function": {"name": "hesapla", "arguments": {"ifade": "1+1"}}, "imza": None}]},
        {"role": "tool", "content": "sonuçlar", "tool_name": "web_ara"},
        {"role": "tool", "content": "2", "tool_name": "hesapla"}])
    icerik = m.cagrilar[0]["contents"]
    assert [c.role for c in icerik] == ["user", "model", "user"]
    fc = icerik[1].parts
    assert fc[0].function_call.name == "web_ara" and fc[0].thought_signature == b"IMZA"
    fr = icerik[2].parts  # ardışık araç cevapları tek içerikte toplanır
    assert [x.function_response.name for x in fr] == ["web_ara", "hesapla"]
    assert fr[0].function_response.response == {"sonuc": "sonuçlar"}


def test_imzasiz_arac_cagrisina_atlama_imzasi_konur(sahte):
    """Hızlı mod ilk aramayı modelsiz yapıp çağrı olarak ekler; Gemini 3 imzasız çağrıyı reddeder."""
    m = sahte(yanit(types.Part(text="x")))
    gs.sohbet("gemini:g", [{"role": "user", "content": "s"},
                           {"role": "assistant", "content": "", "tool_calls": [
                               {"function": {"name": "web_ara", "arguments": {}}}]},
                           {"role": "tool", "content": "r", "tool_name": "web_ara"}])
    assert m.cagrilar[0]["contents"][1].parts[0].thought_signature == b"skip_thought_signature_validator"


@pytest.mark.parametrize("hata,mesaj", [
    (api_hatasi(400, "API key not valid. Please pass a valid API key."), "Gemini anahtarı geçersiz ya da yetkisiz. Ayarlar'dan kontrol et."),
    (api_hatasi(403, "Permission denied"), "Gemini anahtarı geçersiz ya da yetkisiz. Ayarlar'dan kontrol et."),
    (httpx.ConnectError("getaddrinfo failed"), "Gemini'ye ulaşılamadı (internet bağlantısı?)."),
])
def test_hata_cevirisi(sahte, hata, mesaj):
    sahte(hata)
    with pytest.raises(ModelHatasi) as h:
        gs.sohbet("gemini:g", [{"role": "user", "content": "x"}])
    assert str(h.value) == mesaj


def test_429_yeniden_denenir_sonra_kota_mesaji(sahte):
    sahte(api_hatasi(429), api_hatasi(429), yanit(types.Part(text="oldu")))
    assert gs.sohbet("gemini:g", [{"role": "user", "content": "x"}]).metin == "oldu"
    sahte(*[api_hatasi(429)] * 4)
    with pytest.raises(ModelHatasi, match="istek sınırı/kotası doldu"):
        gs.sohbet("gemini:g", [{"role": "user", "content": "x"}])


def test_5xx_yeniden_denenir_sonra_mesaj(sahte):
    sahte(*[api_hatasi(503)] * 4)
    with pytest.raises(ModelHatasi, match="Gemini şu an yanıt vermiyor."):
        gs.sohbet("gemini:g", [{"role": "user", "content": "x"}])


def test_akis_ilk_parcadan_sonra_yeniden_denenmez(sahte):
    def akis():
        yield yanit(types.Part(text="yarım"))
        raise api_hatasi(503)
    m = sahte(akis())
    uretec = gs.sohbet("gemini:g", [{"role": "user", "content": "x"}], akis=True)
    assert next(uretec).metin == "yarım"
    with pytest.raises(ModelHatasi, match="yanıt vermiyor"):
        next(uretec)
    assert len(m.cagrilar) == 1


def test_guvenlik_filtresi(sahte):
    sahte(yanit(engel="SAFETY"))
    with pytest.raises(ModelHatasi, match="güvenlik filtresi"):
        gs.sohbet("gemini:g", [{"role": "user", "content": "x"}])
    sahte(yanit(bitis="SAFETY"))
    with pytest.raises(ModelHatasi, match="güvenlik filtresi"):
        gs.sohbet("gemini:g", [{"role": "user", "content": "x"}])


def test_anahtar_yoksa_anlasilir_hata(sahte):
    ayarlar.gemini_sil()
    with pytest.raises(ModelHatasi, match="anahtarı"):
        gs.sohbet("gemini:g", [{"role": "user", "content": "x"}])


def test_anahtar_hata_metinlerinden_temizlenir(sahte):
    sahte(api_hatasi(400, f"Bad request for key={ANAHTAR} and AIzaSyBASKAANAHTAR0123456789abcdefghijk"))
    with pytest.raises(ModelHatasi) as h:
        gs.sohbet("gemini:g", [{"role": "user", "content": "x"}])
    assert ANAHTAR not in str(h.value) and "AIza" not in str(h.value)
    sahte(api_hatasi(400, "bad request AQ.SAHTEsahteSAHTEsahte0123456789"))  # yeni anahtar biçimi
    with pytest.raises(ModelHatasi) as h:
        gs.sohbet("gemini:g", [{"role": "user", "content": "x"}])
    assert "SAHTEsahte" not in str(h.value)


def _model(ad, eylemler=("generateContent",)):
    return types.Model(name=f"models/{ad}", supported_actions=list(eylemler))


def test_modeller_takma_adlari_tercih_eder_pro_listelenmez(sahte):
    """Kullanıcı kararı: pahalı Pro yok; yalnızca ucuz Flash-Lite ve Flash."""
    sahte([_model("gemini-2.5-flash"), _model("gemini-flash-latest"), _model("gemini-flash-lite-latest"),
           _model("gemini-pro-latest")])
    assert gs.modeller() == [{"ad": "gemini:gemini-flash-lite-latest", "etiket": "Gemini Flash-Lite (bulut, en ucuz)"},
                             {"ad": "gemini:gemini-flash-latest", "etiket": "Gemini Flash (bulut, ucuz ve akıllı)"}]


def test_modeller_takma_ad_yoksa_en_yeni_surum(sahte):
    sahte([_model("gemini-2.5-flash"), _model("gemini-3.1-flash"), _model("gemini-3.1-flash-lite"),
           _model("gemini-2.5-flash-lite"), _model("gemini-3-pro"), _model("gemini-9-flash", ("embedContent",))])
    assert [m["ad"] for m in gs.modeller()] == ["gemini:gemini-3.1-flash-lite", "gemini:gemini-3.1-flash"]


def test_modeller_liste_alinamazsa_takma_adlar_ve_onbellek(sahte):
    sahte(httpx.ConnectError("yok"))
    assert [x["ad"] for x in gs.modeller()] == ["gemini:gemini-flash-lite-latest", "gemini:gemini-flash-latest"]
    m2 = sahte([_model("gemini-flash-latest"), _model("gemini-flash-lite-latest")])
    gs.modeller()
    gs.modeller()
    assert len(m2.cagrilar) == 1  # 1 saat önbellek


def test_anahtar_yoksa_model_listelenmez(sahte):
    ayarlar.gemini_sil()
    assert gs.modeller() == []


def test_anahtar_dogrula(sahte):
    sahte([_model("gemini-flash-latest")])
    gs.anahtar_dogrula("YENI")  # hata vermez
    sahte(api_hatasi(400, "API key not valid"))
    with pytest.raises(ModelHatasi, match="geçersiz"):
        gs.anahtar_dogrula("YANLIS")


def test_yonlendirme_gemini_saglayicisina_gider(sahte):
    sahte(yanit(types.Part(text="yönlendi")))
    assert model.sohbet("gemini:gemini-flash-latest", [{"role": "user", "content": "x"}]).metin == "yönlendi"


def test_istemci_canli_tutulur():
    """Gerçek hata: istemci nesnesi çöpe gidince httpx bağlantısı kapanıyordu ("client has been closed")."""
    import gc
    modeller_ = gs._istemci("AIzaSyCANLI0123456789abcdefghijklmnopqrs").models
    gc.collect()
    assert not modeller_._api_client._httpx_client.is_closed


def test_yalnizca_sistem_mesaji_kullaniciya_tasinir(sahte):
    """Gerçek hata (derin mod): json_sor kullanıcı mesajı olmadan çağrılınca Gemini 'contents are required' verdi."""
    m = sahte(yanit(types.Part(text="{}")))
    gs.sohbet("gemini:g", [{"role": "system", "content": "SADECE SİSTEM"}], json=True)
    k = m.cagrilar[0]
    assert [c.role for c in k["contents"]] == ["user"] and k["contents"][0].parts[0].text == "SADECE SİSTEM"
    assert k["config"].system_instruction is None


def test_kodsuz_api_hatasi_turkce_mesaj(sahte):
    """Kütüphane kodsuz bir APIError verirse 'TypeError' yerine anlaşılır mesaj gelmeli."""
    h = errors.APIError(400, {"error": {"message": "bilinmeyen"}})
    h.code = None
    sahte(h)
    with pytest.raises(ModelHatasi) as e:
        gs.sohbet("gemini:g", [{"role": "user", "content": "x"}])
    assert "TypeError" not in str(e.value) and str(e.value).startswith("Gemini")


def test_istemci_olusturma_hatasi_cevrilir(sahte, monkeypatch):
    monkeypatch.setattr(gs, "_istemci", lambda anahtar: (_ for _ in ()).throw(ValueError(f"bad key {ANAHTAR}")))
    with pytest.raises(ModelHatasi) as e:
        gs.sohbet("gemini:g", [{"role": "user", "content": "x"}])
    assert ANAHTAR not in str(e.value)
