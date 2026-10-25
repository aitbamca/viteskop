"""Henüz üretilmemiş senaryoların yollarını yazar (yapilanlar.txt'ye bakar).
Sayfa sahibinin özel istekleri (oncelikli.txt) her zaman en başta gelir.

Kullanım: python siradaki.py [en_fazla]
"""
import glob
import os
import sys


def satirlar(yol):
    return [s.strip() for s in open(yol, encoding="utf-8") if s.strip()] if os.path.exists(yol) else []


en_fazla = int(sys.argv[1]) if len(sys.argv) > 1 else 3
yapilanlar = set(satirlar("yapilanlar.txt"))
oncelikli = [ad for ad in dict.fromkeys(satirlar("oncelikli.txt")) if os.path.exists(os.path.join("senaryolar", ad))]

bekleyenler = [os.path.join("senaryolar", ad) for ad in oncelikli if ad not in yapilanlar]
bekleyenler += [yol for yol in sorted(glob.glob("senaryolar/*.json"))
                if os.path.basename(yol) not in yapilanlar and os.path.basename(yol) not in oncelikli]
print("\n".join(bekleyenler[:en_fazla]))
