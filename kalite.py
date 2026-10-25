"""Paylaşım öncesi son kontrol: video ve senaryo yayına uygun mu? (özellikle "hemen" paylaşımlar için)

Kullanım: python kalite.py senaryolar/X.json cikti/X.mp4  → sorun yoksa 0, varsa 1 döner ve sorunları yazar.
Ses-yazı uyumu üretimde denetlenir (ses.bol: konuşma hızı kontrolü); burada süre, içerik ve dosya denetlenir.
"""
import json
import re
import subprocess
import sys


def sure(yol):
    cikti = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", yol],
                           capture_output=True, text=True)
    try:
        return float(cikti.stdout.strip())
    except ValueError:
        return 0.0


def kontrol(senaryo_yolu, video_yolu):
    s = json.load(open(senaryo_yolu, encoding="utf-8"))
    sahneler = s.get("sahneler", [])
    kelime = sum(len(sh.get("metin", "").split()) for sh in sahneler)
    sorunlar = []
    if len(sahneler) < 5:
        sorunlar.append(f"{len(sahneler)} sahne (en az 5)")
    if kelime < 85:
        sorunlar.append(f"{kelime} kelime (en az 85: hikâye çok kısa)")
    if not sahneler or sahneler[0].get("tip") != "giris" or sahneler[-1].get("tip") != "kapanis":
        sorunlar.append("ilk sahne giris, son sahne kapanis olmalı")
    for i, sh in enumerate(sahneler, 1):
        tr = len([c for c in re.split(r"(?<=[.!?])\s+", sh.get("metin", "").strip()) if c])
        en = len([c for c in re.split(r"(?<=[.!?])\s+", sh.get("metin_en", "").strip()) if c])
        if sh.get("metin_en") and tr != en:
            sorunlar.append(f"sahne {i}: Türkçe {tr}, İngilizce {en} cümle (altyazı kayar)")
    if not s.get("etiketler"):
        sorunlar.append("hashtag yok")
    sn = sure(video_yolu)
    if not 30 <= sn <= 90:
        sorunlar.append(f"video süresi {sn:.0f} sn (30-90 olmalı)")
    return sorunlar


if __name__ == "__main__":
    sorunlar = kontrol(sys.argv[1], sys.argv[2])
    if sorunlar:
        print("KALİTE KONTROLÜNDEN GEÇMEDİ: " + "; ".join(sorunlar))
        sys.exit(1)
    print("kalite kontrolü tamam")
