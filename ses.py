"""Metni sese çevirir.

Sağlayıcı SES_SAGLAYICI ile seçilir: "gemini", "elevenlabs" ya da "edge".
Seçilen sağlayıcının anahtarı yoksa ya da hata verirse sırayla edge-tts'e, o da olmazsa
çevrimdışı espeak-ng'ye düşer. Bir videonun tüm sahneleri her zaman aynı sesle okunur.

Gemini'nin ücretsiz kotası düşük olduğu için videonun tamamı tek istekte okunur ve ses,
sahneler arasındaki duraklamalardan bölünür.
"""
import asyncio
import base64
import ctypes
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
import wave

import numpy as np

SAGLAYICI = os.environ.get("SES_SAGLAYICI") or "gemini"

GEMINI_MODEL = os.environ.get("GEMINI_SES_MODELI") or "gemini-2.5-flash-preview-tts"
GEMINI_SES = os.environ.get("GEMINI_SES") or "Iapetus"  # net, temiz bir erkek sesi (sayfa sahibi seçti)
GEMINI_TARZ = os.environ.get(
    "GEMINI_TARZ",
    "Read the following Turkish text aloud in Turkish, in a confident, energetic and friendly male voice, "
    "like an experienced car mechanic explaining something clearly to a driver, at a lively natural pace. "
    "Pause for about one second between paragraphs:",
)

ELEVENLABS_SES_ID = os.environ.get("ELEVENLABS_SES_ID") or "XrExE9yKIg1WjnnlVkGX"
ELEVENLABS_MODEL = os.environ.get("ELEVENLABS_MODELI") or "eleven_multilingual_v2"

EDGE_SES = os.environ.get("ANLATICI_SESI") or "tr-TR-AhmetNeural"
EDGE_HIZ = os.environ.get("ANLATICI_HIZI") or "+0%"


def _istek(url, govde, basliklar, deneme=4):
    """JSON POST; kota dolunca (429) ya da sunucu hatasında bekleyip tekrar dener."""
    veri = json.dumps(govde).encode()
    for i in range(deneme):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, veri, basliklar), timeout=120) as yanit:
                return yanit.read()
        except urllib.error.HTTPError as hata:
            icerik = hata.read()
            gunluk_kota = hata.code == 429 and (b"current quota" in icerik or b"quota_exceeded" in icerik or b"PerDay" in icerik)
            if hata.code not in (429, 500, 502, 503) or gunluk_kota or i == deneme - 1:
                raise RuntimeError(f"HTTP {hata.code}: {icerik[:300]!r}") from None  # günlük kota bitince beklemek boşuna
            time.sleep(15 * (i + 1))


def _gemini(metin, hedef_wav):
    anahtar = os.environ["GEMINI_API_KEY"]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    govde = {
        "contents": [{"parts": [{"text": f"{GEMINI_TARZ}\n\n{metin}"}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": GEMINI_SES}}},
        },
    }
    yanit = json.loads(_istek(url, govde, {"Content-Type": "application/json", "x-goog-api-key": anahtar}))
    pcm = base64.b64decode(yanit["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
    with wave.open(hedef_wav, "wb") as w:  # Gemini 24 kHz, 16 bit, mono ham ses döndürür
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(pcm)


def _elevenlabs(metin, hedef_mp3):
    anahtar = os.environ["ELEVENLABS_API_KEY"]
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_SES_ID}?output_format=mp3_44100_128"
    govde = {
        "text": metin,
        "model_id": ELEVENLABS_MODEL,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.3, "speed": 0.92},
    }
    with open(hedef_mp3, "wb") as f:
        f.write(_istek(url, govde, {"Content-Type": "application/json", "xi-api-key": anahtar}))


def _edge_tts(metin, hedef_mp3):
    import edge_tts

    async def calis():
        await edge_tts.Communicate(metin, EDGE_SES, rate=EDGE_HIZ, pitch="+4Hz").save(hedef_mp3)

    asyncio.run(asyncio.wait_for(calis(), timeout=60))


def _espeak(metin, hedef_wav):
    import espeakng_loader

    lib = ctypes.CDLL(espeakng_loader.get_library_path())
    veri_klasoru = os.path.dirname(espeakng_loader.get_data_path())
    ornek_hizi = lib.espeak_Initialize(2, 0, veri_klasoru.encode(), 0)  # 2 = senkron
    parcalar = []
    CALLBACK = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_short), ctypes.c_int, ctypes.c_void_p)

    @CALLBACK
    def topla(wav, adet, _olaylar):
        if adet > 0:
            parcalar.append(ctypes.string_at(wav, adet * 2))
        return 0

    lib.espeak_SetSynthCallback(topla)
    lib.espeak_SetVoiceByName(b"tr")
    lib.espeak_SetParameter(1, 140, 0)  # konuşma hızı
    lib.espeak_SetParameter(3, 60, 0)  # ses perdesi
    veri = metin.encode("utf-8") + b"\0"
    lib.espeak_Synth(veri, len(veri), 0, 0, 0, 1, None, None)  # 1 = UTF-8
    lib.espeak_Synchronize()
    with wave.open(hedef_wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(ornek_hizi)
        w.writeframes(b"".join(parcalar))


MOTORLAR = {"gemini": _gemini, "elevenlabs": _elevenlabs, "edge-tts": _edge_tts, "espeak-ng": _espeak}
ANAHTARLAR = {"gemini": "GEMINI_API_KEY", "elevenlabs": "ELEVENLABS_API_KEY"}


def _anahtar_var(motor):
    return motor not in ANAHTARLAR or bool(os.environ.get(ANAHTARLAR[motor], ""))


def _sira():
    """Seçilen sağlayıcı, sonra anahtarı olan diğer kaliteli sağlayıcılar, en son ücretsiz yedekler."""
    secilen = "edge-tts" if SAGLAYICI == "edge" else SAGLAYICI
    sira = [m for m in [secilen, "gemini", "elevenlabs"] if m in ANAHTARLAR or m == secilen]
    sira = [m for m in dict.fromkeys(sira) if _anahtar_var(m)]
    return sira + [m for m in ("edge-tts", "espeak-ng") if m not in sira]


_dusenler = set()  # hata veren motorlar; aynı çalıştırmada bir daha denenmez
TEK_ISTEKLI = {"gemini"}  # tüm video tek istekte okunur


def _wav_yap(kaynak, hedef_wav):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", kaynak, "-ar", "44100", "-ac", "1", hedef_wav], check=True)
    os.remove(kaynak)


def _oku(yol):
    with wave.open(yol) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768, w.getframerate()


def _yaz(yol, veri, hiz):
    with wave.open(yol, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(hiz)
        w.writeframes((np.clip(veri, -1, 1) * 32767).astype(np.int16).tobytes())


def _sessizlikler(veri, hiz, en_kisa=0.25):
    """(başlangıç, bitiş) saniye listesi: sesin kısıldığı aralıklar."""
    pencere = int(hiz * 0.02)
    enerji = np.sqrt(np.mean(veri[: len(veri) // pencere * pencere].reshape(-1, pencere) ** 2, axis=1))
    sessiz = enerji < max(enerji.max() * 0.04, 1e-4)
    sonuc, bas = [], None
    for i, s in enumerate(np.append(sessiz, False)):
        if s and bas is None:
            bas = i
        elif not s and bas is not None:
            if (i - bas) * 0.02 >= en_kisa:
                sonuc.append((bas * 0.02, i * 0.02))
            bas = None
    return sonuc


def _kirp(parca, hiz, pay=0.05):
    """Baştaki ve sondaki sessizliği at (biraz pay bırakarak)."""
    esik = max(np.abs(parca).max() * 0.04, 1e-4) if len(parca) else 1
    dolu = np.where(np.abs(parca) > esik)[0]
    if not len(dolu):
        return parca
    return parca[max(0, dolu[0] - int(pay * hiz)): dolu[-1] + int(pay * hiz)]


def bol(toplu_wav, metinler, hedefler):
    """Tek parça sesi sahnelere böler: beklenen sınırlara en yakın uzun duraklamaları seçer."""
    veri, hiz = _oku(toplu_wav)
    veri = _kirp(veri, hiz, pay=0)
    toplam = len(veri) / hiz
    agirlik = np.cumsum([len(m) for m in metinler]) / sum(len(m) for m in metinler)
    beklenen = [a * toplam for a in agirlik[:-1]]
    ortalama = toplam / len(metinler)
    adaylar = _sessizlikler(veri, hiz)
    kesimler, onceki = [], 0.0
    for b in beklenen:
        uygun = [(bas, bit) for bas, bit in adaylar if (bas + bit) / 2 > onceki + 0.5]
        if uygun:
            bas, bit = max(uygun, key=lambda a: (a[1] - a[0]) - 1.5 * abs((a[0] + a[1]) / 2 - b) / ortalama)
            kesim = (bas + bit) / 2
        else:
            kesim = max(b, onceki + 0.5)
        kesimler.append(kesim)
        onceki = kesim
    sinirlar = [0.0] + kesimler + [toplam]
    for i, hedef in enumerate(hedefler):
        _yaz(hedef, _kirp(veri[int(sinirlar[i] * hiz): int(sinirlar[i + 1] * hiz)], hiz), hiz)
    return kesimler


def _tek(motor, metin, hedef_wav):
    gecici = hedef_wav + ".kaynak"
    MOTORLAR[motor](metin, gecici)
    _wav_yap(gecici, hedef_wav)


# ör. "gemini,elevenlabs": bunlardan biri çalışmazsa video robotik yedek sesle üretilmez, beklenir
IZINLI = {m.strip() for m in os.environ.get("SES_ZORUNLU", "").split(",") if m.strip()}


class SesYok(RuntimeError):
    pass


def seslendir_hepsi(metinler, hedefler):
    """Tüm sahneleri aynı motorla 44.1 kHz wav olarak yazar, kullanılan motoru döndürür."""
    for motor in [m for m in _sira() if m not in _dusenler]:
        if IZINLI and motor not in IZINLI:
            raise SesYok(f"{', '.join(sorted(IZINLI))} şu an kullanılamıyor; video yedek sesle üretilmedi, sonra tekrar denenecek.")
        try:
            if motor in TEK_ISTEKLI and len(metinler) > 1:
                toplu = hedefler[0] + ".toplu.wav"
                _tek(motor, "\n\n".join(metinler), toplu)
                bol(toplu, metinler, hedefler)
                os.remove(toplu)
            else:
                for metin, hedef in zip(metinler, hedefler):
                    _tek(motor, metin, hedef)
            return motor
        except Exception as hata:
            _dusenler.add(motor)
            print(f"  {motor} kullanılamadı ({type(hata).__name__}: {str(hata)[:200]}), sıradakine geçiliyor")
    raise RuntimeError("Hiçbir ses motoru çalışmadı.")


def seslendir(metin, hedef_wav):
    """Tek bir metni seslendirir, kullanılan motoru döndürür."""
    return seslendir_hepsi([metin], [hedef_wav])


def sure(wav_yolu):
    with wave.open(wav_yolu) as w:
        return w.getnframes() / w.getframerate()
