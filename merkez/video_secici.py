"""Hazır video adaylarını deterministik sırayla üretir (mevcut paylasilacak.py mantığı + 'hazir' release varlığı).

Sıra: oncelikli.txt (üretilmiş olanlar) önce, sonra yapilanlar.txt sırası; yayinlananlar.txt'dekiler hariç.
Yalnız `hazir` release'inde `<ad>.mp4` varlığı bulunan adaylar döner (indirilemeyecek video seçilmez).
Kimlik (kilit anahtarı) = senaryo dosya adı, uzantısız; ref için güvenli karakterlere indirgenir.
"""
import json
import os
import re

from .yayin_calistir import Video


def _satirlar(yol):
    if not os.path.exists(yol):
        return []
    with open(yol, encoding="utf-8") as f:
        return [s.strip() for s in f if s.strip()]


def guvenli_kimlik(ad):
    return re.sub(r"[^A-Za-z0-9._-]", "_", ad[:-5] if ad.endswith(".json") else ad)


def adaylar(kok=".", hazir_adlar=None, aciklama_yaz=None):
    """hazir_adlar: release'deki varlık adları kümesi (None = denetleme yok, yalnız test/dry)."""
    yayinlanan = {s.split("\t")[0] for s in _satirlar(os.path.join(kok, "yayinlananlar.txt"))}
    uretilen = list(dict.fromkeys(_satirlar(os.path.join(kok, "yapilanlar.txt"))))
    oncelik = [a for a in dict.fromkeys(_satirlar(os.path.join(kok, "oncelikli.txt"))) if a in uretilen]
    for ad in dict.fromkeys(oncelik + uretilen):
        yol = os.path.join(kok, "senaryolar", ad)
        if ad in yayinlanan or not os.path.exists(yol):
            continue
        if hazir_adlar is not None and ad[:-5] + ".mp4" not in hazir_adlar:
            continue
        with open(yol, encoding="utf-8") as f:
            senaryo = json.load(f)
        yield Video(guvenli_kimlik(ad), yol, senaryo_id=ad, surum=senaryo.get("surum", 1),
                    aciklama=aciklama_yaz(senaryo) if aciklama_yaz else senaryo.get("aciklama", ""),
                    kapak_ms=senaryo.get("kapak_ms", 2500))
