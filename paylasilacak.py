"""Üretilmiş ama henüz paylaşılmamış ilk senaryonun dosya adını yazar.

yapilanlar.txt: üretilen senaryolar (üretim sırasıyla)
yayinlananlar.txt: "dosya<TAB>zaman<TAB>medya kimliği" satırları
oncelikli.txt: sayfa sahibinin özel istekleri; hazır olunca planlı videoların önüne geçer (ilk boş paylaşım saati)
"""
import os


def satirlar(yol):
    if not os.path.exists(yol):
        return []
    return [s.strip() for s in open(yol, encoding="utf-8") if s.strip()]


yayinlananlar = {s.split("\t")[0] for s in satirlar("yayinlananlar.txt")}
uretilenler = list(dict.fromkeys(satirlar("yapilanlar.txt")))  # sırayı koruyarak tekrarları at
sira = [ad for ad in dict.fromkeys(satirlar("oncelikli.txt")) if ad in uretilenler] + uretilenler
for ad in sira:
    if ad not in yayinlananlar and os.path.exists(os.path.join("senaryolar", ad)):
        print(ad)
        break
