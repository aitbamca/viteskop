"""Henüz üretilmemiş senaryoların yollarını yazar (yapilanlar.txt'ye bakar).

Kullanım: python siradaki.py [en_fazla]
"""
import glob
import os
import sys

en_fazla = int(sys.argv[1]) if len(sys.argv) > 1 else 3
yapilanlar = set()
if os.path.exists("yapilanlar.txt"):
    yapilanlar = {satir.strip() for satir in open("yapilanlar.txt", encoding="utf-8") if satir.strip()}

bekleyenler = [yol for yol in sorted(glob.glob("senaryolar/*.json")) if os.path.basename(yol) not in yapilanlar]
print("\n".join(bekleyenler[:en_fazla]))
