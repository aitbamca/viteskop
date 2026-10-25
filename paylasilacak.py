"""Üretilmiş ama henüz paylaşılmamış ilk senaryonun dosya adını yazar.

yapilanlar.txt: üretilen senaryolar (üretim sırasıyla)
yayinlananlar.txt: "dosya<TAB>zaman<TAB>medya kimliği" satırları
"""
import os


def satirlar(yol):
    if not os.path.exists(yol):
        return []
    return [s.strip() for s in open(yol, encoding="utf-8") if s.strip()]


yayinlananlar = {s.split("\t")[0] for s in satirlar("yayinlananlar.txt")}
for ad in dict.fromkeys(satirlar("yapilanlar.txt")):  # sırayı koruyarak tekrarları at
    if ad not in yayinlananlar and os.path.exists(os.path.join("senaryolar", ad)):
        print(ad)
        break
