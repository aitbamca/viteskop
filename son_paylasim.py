"""Son paylaşım N saatten yeniyse 0 döner (yedek zamanlamanın çift paylaşım yapmaması için).

Kullanım: python son_paylasim.py 3
"""
import datetime
import sys

saat = float(sys.argv[1]) if len(sys.argv) > 1 else 3
try:
    satirlar = [s.rstrip("\n").split("\t") for s in open("yayinlananlar.txt", encoding="utf-8") if s.strip()]
except FileNotFoundError:
    satirlar = []
zamanlar = [datetime.datetime.strptime(s[1], "%Y-%m-%dT%H:%MZ") for s in satirlar if len(s) > 1]
son = max(zamanlar, default=None)
simdi = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
sys.exit(0 if son and simdi - son < datetime.timedelta(hours=saat) else 1)
