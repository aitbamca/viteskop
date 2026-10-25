"""Bir senaryo JSON'undan dikey (9:16) Viteskop videosu üretir.

Kullanım: python3 video.py senaryolar/ornek.json [cikti.mp4]
Sahne tipleri ve senaryo biçimi: SENARYO.md
"""
import importlib.util
import json
import math
import os
import random
import re
import subprocess
import sys
import tempfile
import wave
from types import SimpleNamespace

import numpy as np
from PIL import Image, ImageDraw

import cizim as c
import ses
import tema as tm

FPS = 24
SR = 44100
BASTA_BOSLUK, SAHNE_ARASI, SONDA_BOSLUK = 0.4, 0.6, 1.0
ACILIS, KAPANIS_KARTI = 0.0, 2.6  # logo kartlarının süresi (açılışta kart yok: video doğrudan soruyla başlar)
GECIS_SURESI = 0.45  # sahne geçişi (saniye)

ALTYAZI_UST, ALTYAZI_GENISLIK, ALTYAZI_FONT, SATIR = 1190, 900, 58, 76
EN_FONT, EN_SATIR = 38, 50  # Türkçenin altındaki İngilizce altyazı


# ---------------------------------------------------------------- zamanlama

def kelime_zamanlari(metin, sure):
    """Sesin süresini kelimelere harf sayısı ve noktalama duraklarına göre paylaştırır."""
    kelimeler = metin.split()
    agirlik = [len(k) + (7 if k[-1] in ".!?" else 4 if k[-1] in ",:" else 1) for k in kelimeler]
    toplam, t, sonuc = sum(agirlik), 0.0, []
    for k, a in zip(kelimeler, agirlik):
        d = sure * a / toplam
        sonuc.append((k, t, t + d))
        t += d
    return sonuc


def cumleler(kz):
    sonuc, simdiki = [], []
    for oge in kz:
        simdiki.append(oge)
        if oge[0][-1] in ".!?":
            sonuc.append(simdiki)
            simdiki = []
    if simdiki:
        sonuc.append(simdiki)
    return sonuc


# ---------------------------------------------------------------- sahneler

SOL = 80  # sol kenar boşluğu: yazılar sola yaslı (ciddi, dergi düzeni)
SOLUK = (150, 158, 174)
SAG_RENK = (150, 178, 214)  # kıyasta sağdaki arabanın rengi (soldaki serinin rengi)
CIZGI = (232, 236, 243)


class Baglam:
    """Sahne fonksiyonlarına verilen bilgiler: sahne(z, t, s) içinde s olarak gelir."""

    def __init__(self, veri, sure, kz, v, ortak, tema_=None, baslik="", senaryo=None):
        self.veri, self.sure, self.kz = veri, sure, kz
        self.tema, self.baslik = tema_, baslik  # temanın renkleri (s.tema["vurgu"] vb.) ve video başlığı
        self.v, self.ortak = v, ortak  # konuya özel çizimler, ortak çizimler (logo vb.)
        self.senaryo = senaryo or {}

    def zaman(self, kelime, varsayilan=None, sira=0):
        """Metindeki bir kelimenin okunduğu saniye (bulunamazsa varsayılan, o da yoksa sahnenin ortası)."""
        return c.zaman_bul(self.kz, kelime, self.sure * 0.5 if varsayilan is None else varsayilan, sira)

    def sirali(self, adet, anahtarlar=None, bas=0.15, son=0.8):
        """adet öğenin beliriş anları: anahtar kelime okununca, yoksa sahneye eşit dağılmış."""
        anlar = []
        for i in range(adet):
            varsayilan = self.sure * (bas + (son - bas) * i / max(1, adet - 1)) if adet > 1 else self.sure * bas
            kelime = anahtarlar[i] if anahtarlar and i < len(anahtarlar) else None
            anlar.append(self.zaman(c.sadelestir(kelime), varsayilan) if kelime else varsayilan)
        return anlar


ORTAK_ARKA_PLANLAR = {}  # bütün sahneler temanın stüdyosunda geçer


def ortak_varliklar():
    l = c.logo(400)
    return SimpleNamespace(logo_kucuk=c.olcekle(l, 64 / l.height) if l.height > l.width * 0.5 else c.olcekle(l, 190 / l.width))


def _yazi(z, metin, x, y, boyut, renk=CIZGI, alfa=1.0, kalin=True, anchor="lm", aralik=0):
    """Saydamlığı olan yazı; aralik > 0 ise harfler aralıklı (küçük büyük harf etiketleri için)."""
    if alfa <= 0 or not metin:
        return
    d = ImageDraw.Draw(z, "RGBA")
    renk = tuple(renk[:3]) + (int(255 * min(1.0, alfa)),)
    f = c.font(boyut, kalin)
    if not aralik:
        d.text((x, y), metin, font=f, fill=renk, anchor=anchor)
        return
    genislik = sum(f.getlength(h) for h in metin) + aralik * (len(metin) - 1)
    if anchor[0] == "m":
        x -= genislik / 2
    elif anchor[0] == "r":
        x -= genislik
    for h in metin:
        d.text((x, y), h, font=f, fill=renk, anchor="l" + anchor[1])
        x += f.getlength(h) + aralik


def _ust_etiket(z, metin, x, y, renk, alfa=1.0, cizgi=True):
    """Turuncu ince çizgi + aralıklı büyük harf etiket: — BAKIM SAATİ"""
    if alfa <= 0:
        return
    d = ImageDraw.Draw(z, "RGBA")
    if cizgi:
        d.line([(x, y), (x + 46 * alfa, y)], fill=tuple(renk[:3]) + (int(255 * alfa),), width=4)
        x += 62
    _yazi(z, metin.upper(), x, y, 30, renk, alfa, aralik=5)


def _cubuk(z, x0, y, uzunluk, kalinlik, renk, alfa=1.0, yon=1):
    if uzunluk <= 0 or alfa <= 0:
        return
    d = ImageDraw.Draw(z, "RGBA")
    x1 = x0 + uzunluk * yon
    d.rectangle((min(x0, x1), y - kalinlik / 2, max(x0, x1), y + kalinlik / 2), fill=tuple(renk[:3]) + (int(255 * alfa),))


def _sayi(metin):
    m = re.search(r"\d+(?:[.,]\d+)?", str(metin).replace(".", "") if re.search(r"\d\.\d{3}", str(metin)) else str(metin))
    return float(m.group().replace(",", ".")) if m else None


def _arac_tanimi(s):
    return s.veri.get("araba") or s.senaryo.get("araba") or {}


def sahne_giris(z, t, s):
    """Seri etiketi ve sola yaslı büyük başlık; altta arabanın teknik çizimi yavaşça kayar."""
    t += BASTA_BOSLUK
    vurgu = s.tema["vurgu"]
    seri = c.SERILER.get(s.senaryo.get("seri"), {})
    tanim = _arac_tanimi(s)
    ar = c.araba_cizgi(820, tanim.get("tip", "sedan"), vurgu=vurgu, teker_aci=t * 30)
    giris = c.kayarak(t, 0.0, 1.2)
    c.yapistir(z, c.saydamlik(ar, 0.85 * giris), 180 - (1 - giris) * 120 + t * 8, 1170 - ar.height)
    _ust_etiket(z, seri.get("ad", "VİTESKOP"), SOL, 470, vurgu, c.kayarak(t, 0.0, 0.4))
    boyut = 104 if len(s.baslik) < 24 else 90
    satirlar = c.satirlara_sar(s.baslik, boyut, 900)
    for i, satir in enumerate(satirlar):
        a = c.kayarak(t, 0.1 + i * 0.12, 0.45)
        _yazi(z, satir, SOL, 570 + i * boyut * 1.12 + (1 - a) * 40, boyut, vurgu if i == len(satirlar) - 1 else CIZGI, a)
    _cubuk(z, SOL, 570 + len(satirlar) * boyut * 1.12 - 10, 220 * c.kayarak(t, 0.6, 0.6), 8, vurgu)


def sahne_bilgi(z, t, s):
    """Büyük yazı: {"tip": "bilgi", "yazi": "...", "metin": "..."}"""
    vurgu = s.tema["vurgu"]
    satirlar = c.satirlara_sar(s.veri.get("yazi", ""), 84, 880)
    y0 = 700 - (len(satirlar) - 1) * 50
    a0 = c.kayarak(t, 0.0, 0.5)
    ImageDraw.Draw(z, "RGBA").rectangle((SOL, y0 - 60, SOL + 8, y0 - 60 + (len(satirlar) * 100 + 20) * a0), fill=vurgu + (255,))
    for i, satir in enumerate(satirlar):
        a = c.kayarak(t, 0.1 + i * 0.1, 0.4)
        _yazi(z, satir, SOL + 40 + (1 - a) * 30, y0 + i * 100, 84, vurgu if i == 0 else CIZGI, a)


def sahne_kiyas(z, t, s):
    """İki araba ve satır satır karşılaştırma çubukları.

    {"tip": "kiyas", "sol": {"ad": "Togg T10X", "tip": "suv"}, "sag": {...},
     "satirlar": [{"ad": "Bagaj", "sol": "441 L", "sag": "510 L", "anahtar": "bagaj"}]}
    Tarafsız: kazanan seçilmez, çubuklar yalnızca rakamları gösterir.
    """
    vurgu = s.tema["vurgu"]
    sol, sag = s.veri.get("sol", {}), s.veri.get("sag", {})
    a = c.kayarak(t, 0.0, 0.7)
    a1 = c.araba_cizgi(440, sol.get("tip", "sedan"), yon=1, vurgu=vurgu)
    a2 = c.araba_cizgi(440, sag.get("tip", "sedan"), yon=-1, vurgu=SAG_RENK)
    c.yapistir(z, c.saydamlik(a1, a), 40 - (1 - a) * 80, 330)
    c.yapistir(z, c.saydamlik(a2, a), 600 + (1 - a) * 80, 330)
    _yazi(z, sol.get("ad", "").upper(), SOL, 545, 34, CIZGI, c.kayarak(t, 0.3, 0.4), aralik=2)
    _yazi(z, sag.get("ad", "").upper(), 1000, 545, 34, CIZGI, c.kayarak(t, 0.4, 0.4), anchor="rm", aralik=2)
    _yazi(z, "VS", 540, 545, 30, vurgu, c.kayarak(t, 0.5, 0.4), anchor="mm", aralik=4)
    ImageDraw.Draw(z, "RGBA").line([(SOL, 585), (1000, 585)], fill=(255, 255, 255, int(40 * a)), width=2)
    satirlar = s.veri.get("satirlar", [])[:5]
    anlar = s.sirali(len(satirlar), [r.get("anahtar") for r in satirlar], bas=0.18, son=0.82)
    for i, (satir, t0) in enumerate(zip(satirlar, anlar)):
        g = c.kayarak(t, t0, 0.5)
        if not g:
            continue
        y = 650 + i * 104
        _yazi(z, satir.get("ad", "").upper(), 540, y, 26, SOLUK, g, anchor="mm", aralik=3)
        n1, n2 = _sayi(satir.get("sol")), _sayi(satir.get("sag"))
        en = max(n1 or 0, n2 or 0)
        oran1 = (n1 / en) if en and n1 is not None and n2 is not None else 1.0
        oran2 = (n2 / en) if en and n1 is not None and n2 is not None else 1.0
        # Tarafsızız: kazanan işaretlenmez, her arabanın çubuğu hep kendi renginde
        _cubuk(z, 530, y + 38, 330 * oran1 * g, 14, vurgu, yon=-1)
        _cubuk(z, 550, y + 38, 330 * oran2 * g, 14, SAG_RENK, yon=1)
        _yazi(z, str(satir.get("sol", "")), SOL, y, 40, CIZGI, g)
        _yazi(z, str(satir.get("sag", "")), 1000, y, 40, CIZGI, g, anchor="rm")


def sahne_araba(z, t, s):
    """Arabanın teknik çizimi ve parçalarına çizgiyle bağlı etiketler.

    {"tip": "araba", "araba": {"tip": "sedan"}, "yazi": "...",
     "etiketler": [{"yazi": "Lastik", "x": 0.22, "y": 0.85, "anahtar": "lastik"}]}
    """
    vurgu = s.tema["vurgu"]
    tanim = _arac_tanimi(s)
    a = c.kayarak(t, 0.0, 1.0)
    ar = c.araba_cizgi(940, tanim.get("tip", "sedan"), vurgu=vurgu, teker_aci=a * 200)
    x0, y0 = 70 - (1 - a) * 160, 760
    c.yapistir(z, c.saydamlik(ar, a), x0, y0)
    if s.veri.get("yazi"):
        _ust_etiket(z, s.veri["yazi"], SOL, 400, vurgu, c.kayarak(t, 0.3, 0.4))
    etiketler = s.veri.get("etiketler", [])[:4]
    anlar = s.sirali(len(etiketler), [e.get("anahtar") for e in etiketler], bas=0.3, son=0.8)
    d = ImageDraw.Draw(z, "RGBA")
    for i, (e, t0) in enumerate(zip(etiketler, anlar)):
        g = c.kayarak(t, max(t0, 0.9), 0.4)
        if not g:
            continue
        px, py = x0 + e.get("x", 0.5) * ar.width, y0 + e.get("y", 0.5) * ar.height
        ey = 520 + (i % 2) * 90
        d.line([(px, py), (px, py - (py - ey - 20) * g)], fill=vurgu + (int(230 * g),), width=3)
        d.ellipse((px - 9, py - 9, px + 9, py + 9), outline=vurgu + (255,), width=3)
        tx = max(SOL, min(1000 - c.font(40).getlength(e.get("yazi", "")), px - 20))
        _yazi(z, e.get("yazi", ""), tx, ey, 40, CIZGI, g)


def sahne_ikaz(z, t, s):
    """Gösterge paneli ve ikaz lambası: {"tip": "ikaz", "ikon": "motor", "renk": "sari", "yazi": "..."}"""
    renk = c.IKAZ_RENKLERI.get(s.veri.get("renk", "sari"), c.KEHRIBAR)
    a = c.kayarak(t, 0.0, 0.5)
    panel = c.kart(960, 420, renk=(6, 8, 12, 235), cerceve=(60, 66, 80, 255), r=28)
    c.ortala_yapistir(z, c.saydamlik(panel, a), 540, 700)
    if a < 0.3:
        return
    sol = c.gosterge(140, 0.22 + 0.04 * math.sin(t * 1.4), renk=(90, 120, 170), yazi="km/s")
    sag = c.gosterge(140, 0.3 + 0.05 * math.sin(t * 1.1 + 1), renk=(90, 120, 170), yazi="x1000")
    c.ortala_yapistir(z, c.saydamlik(sol, a), 225, 700)
    c.ortala_yapistir(z, c.saydamlik(sag, a), 855, 700)
    yanip = 0.5 + 0.5 * math.cos(max(0.0, t - 0.4) * 5) if s.veri.get("yanip", s.veri.get("renk") == "kirmizi") else 1.0
    lamba = c.ikaz_lambasi(s.veri.get("ikon", "motor"), 210, renk, parlak=yanip if t > 0.4 else 0.15)
    c.ortala_yapistir(z, lamba, 540, 700)
    if s.veri.get("yazi"):
        _ust_etiket(z, s.veri["yazi"], SOL, 990, renk, c.kayarak(t, 0.6, 0.4))


def sahne_liste(z, t, s):
    """Numaralı maddeler: {"tip": "liste", "maddeler": ["...", "..."], "anahtarlar": [...], "baslik": "isteğe bağlı"}"""
    vurgu = s.tema["vurgu"]
    maddeler = s.veri.get("maddeler", [])[:5]
    anlar = s.sirali(len(maddeler), s.veri.get("anahtarlar"), bas=0.1, son=0.75)
    y = 400
    if s.veri.get("baslik"):
        _ust_etiket(z, s.veri["baslik"], SOL, 380, vurgu, c.kayarak(t, 0.0, 0.4))
        y = 450
    d = ImageDraw.Draw(z, "RGBA")
    for i, (madde, t0) in enumerate(zip(maddeler, anlar)):
        satirlar = c.satirlara_sar(madde, 46, 760)
        yuk = 40 + len(satirlar) * 56
        g = c.kayarak(t, t0, 0.45)
        if g:
            kx = (1 - g) * -40
            _yazi(z, f"{i + 1:02d}", SOL + kx, y + yuk / 2, 54, vurgu, g)
            for j, satir in enumerate(satirlar):
                _yazi(z, satir, SOL + 120 + kx, y + yuk / 2 + (j - (len(satirlar) - 1) / 2) * 56, 46, CIZGI, g)
            d.line([(SOL, y + yuk + 10), (SOL + 920 * g, y + yuk + 10)], fill=(255, 255, 255, 34), width=2)
        y += yuk + 22


_parca_onbellek = {}


def sahne_parca(z, t, s):
    """Parçanın teknik çizimi ve notlar: {"tip": "parca", "parca": "fren_diski", "yazi": "Fren diski", "notlar": ["...", "..."]}"""
    vurgu = s.tema["vurgu"]
    ad = s.veri.get("parca", "lastik")
    a = c.kayarak(t, 0.0, 0.6)
    aci = (int(t * 12) % 360) // 3 * 3 if ad in ("lastik", "fren_diski") else 0
    if (ad, aci) not in _parca_onbellek:
        if len(_parca_onbellek) > 160:
            _parca_onbellek.clear()
        _parca_onbellek[(ad, aci)] = c.parca_cizgi(ad, 470, aci=aci)
    resim = _parca_onbellek[(ad, aci)]
    c.ortala_yapistir(z, c.saydamlik(c.olcekle(resim, 0.92 + 0.08 * a), a), 540, 640)
    if s.veri.get("yazi"):
        _ust_etiket(z, "PARÇA", SOL, 940, vurgu, c.kayarak(t, 0.3, 0.4))
        _yazi(z, s.veri["yazi"], SOL, 1010, 72, CIZGI, c.kayarak(t, 0.4, 0.4))
    notlar = s.veri.get("notlar", [])[:3]
    anlar = s.sirali(len(notlar), s.veri.get("anahtarlar"), bas=0.3, son=0.75)
    d = ImageDraw.Draw(z, "RGBA")
    for i, (n, t0) in enumerate(zip(notlar, anlar)):
        g = c.kayarak(t, t0, 0.4)
        if not g:
            continue
        sag = i % 2 == 1
        y = 430 + i * 150
        x = 1000 if sag else SOL
        d.line([(x - 6 if sag else x + 6, y + 30), (x - 120 if sag else x + 120, y + 30)], fill=vurgu + (int(255 * g),), width=3)
        _yazi(z, n, x, y, 38, CIZGI, g, anchor="rm" if sag else "lm")


def sahne_gosterge(z, t, s):
    """Gösterge iğnesi bir değere çıkar: {"tip": "gosterge", "deger": 0.7, "yazi": "10.000 km", "alt": "yağ değişimi"}"""
    vurgu = s.tema["vurgu"]
    a = c.kayarak(t, 0.0, 0.5)
    hedef = float(s.veri.get("deger", 0.7))
    x = c.kayarak(t, 0.3, 1.6)
    resim = c.gosterge(320, hedef * x, renk=vurgu, yazi=s.veri.get("yazi") if x > 0.5 else None, alt_yazi=s.veri.get("alt"))
    c.ortala_yapistir(z, c.saydamlik(resim, a), 540, 700)


def sahne_uyari(z, t, s):
    """Güvenlik notu: {"tip": "uyari", "yazi": "Fren işini ustaya bırak!"}"""
    vurgu = c.KEHRIBAR
    a = c.kayarak(t, 0.0, 0.5)
    k = c.Kalem(180, 160)
    k.cokgen([(90, 8), (172, 150), (8, 150)], outline=vurgu, width=7)
    k.kutu((83, 52, 97, 108), fill=vurgu, r=5)
    k.daire(90, 128, 8, fill=vurgu)
    c.yapistir(z, c.saydamlik(k.bitir(), a), SOL, 420)
    _ust_etiket(z, "GÜVENLİK NOTU", SOL + 210, 500, vurgu, a, cizgi=False)
    satirlar = c.satirlara_sar(s.veri.get("yazi", ""), 72, 880)
    for i, satir in enumerate(satirlar):
        g = c.kayarak(t, 0.3 + i * 0.12, 0.45)
        _yazi(z, satir, SOL + (1 - g) * 30, 680 + i * 92, 72, CIZGI, g)
    ImageDraw.Draw(z, "RGBA").rectangle((SOL, 640, SOL + 920 * c.kayarak(t, 0.2, 0.6), 644), fill=vurgu + (200,))


def sahne_kapanis(z, t, s):
    """Serinin sorusu (ya da senaryodaki "soru") ve yorum/kaydet çağrısı."""
    vurgu = s.tema["vurgu"]
    seri = c.SERILER.get(s.senaryo.get("seri"), {})
    soru = s.veri.get("soru") or s.senaryo.get("soru") or seri.get("soru") or "Sen ne düşünüyorsun?"
    _ust_etiket(z, "SIRA SENDE", SOL, 470, vurgu, c.kayarak(t, 0.0, 0.4))
    satirlar = c.satirlara_sar(soru, 88, 900)
    for i, satir in enumerate(satirlar):
        g = c.kayarak(t, 0.15 + i * 0.12, 0.45)
        _yazi(z, satir, SOL, 570 + i * 100 + (1 - g) * 30, 88, CIZGI, g)
    y = 600 + len(satirlar) * 100
    for j, (yazi_, kelime, oran) in enumerate([("Yorumlara yaz", "yorum", 0.45), ("Kaydet, lazım olur", "kaydet", 0.65)]):
        g = c.kayarak(t, s.zaman(kelime, s.sure * oran), 0.4)
        _yazi(z, "→", SOL, y + j * 74, 46, vurgu, g)
        _yazi(z, yazi_, SOL + 70, y + j * 74, 46, CIZGI, g)


ORTAK_SAHNELER = {"giris": sahne_giris, "bilgi": sahne_bilgi, "kiyas": sahne_kiyas, "araba": sahne_araba,
                  "ikaz": sahne_ikaz, "liste": sahne_liste, "parca": sahne_parca, "gosterge": sahne_gosterge,
                  "uyari": sahne_uyari, "kapanis": sahne_kapanis}


def sahne_modulu(senaryo_yolu):
    """senaryolar/ad.json'un yanında ad.py varsa onu yükler (konuya özel sahneler)."""
    yol = os.path.splitext(senaryo_yolu)[0] + ".py"
    if not os.path.exists(yol):
        return SimpleNamespace(ARKA_PLANLAR={}, SAHNELER={}, hazirla=lambda: None)
    spec = importlib.util.spec_from_file_location("konu_sahneleri", yol)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def arka_plan_yap(tanim, tema_, ek):
    """Konu modülü resim fonksiyonu verdiyse onu, renk çifti verdiyse o gökyüzüyle temanın dünyasını kullanır."""
    if callable(tanim):
        return tanim()
    return tm.ortam(tema_, ek, gok=tanim)


# ---------------------------------------------------------------- yazılar

def baslik(z, metin, ortak, soru_goster=True, seri=None, vurgu=c.TURUNCU_MARKA, ilerleme=None):
    """Üst bant: ilerleme çizgisi, solda logo, sağda seri; konu sahnelerinde başlık sola yaslı."""
    d = ImageDraw.Draw(z, "RGBA")
    if ilerleme is not None:
        d.rectangle((0, 0, c.W, 6), fill=(255, 255, 255, 40))
        d.rectangle((0, 0, c.W * ilerleme, 6), fill=vurgu + (255,))
    c.yapistir(z, ortak.logo_kucuk, SOL, 100 - ortak.logo_kucuk.height / 2)
    bilgi = c.SERILER.get(seri)
    if bilgi:
        _yazi(z, bilgi["ad"], 1000, 100, 26, vurgu, anchor="rm", aralik=4)
    if soru_goster:
        _yazi(z, metin, SOL, 215, 46 if len(metin) < 30 else 40, CIZGI, 0.85)
        d.rectangle((SOL, 255, SOL + 70, 259), fill=vurgu + (255,))


def satirlara_bol(kelimeler):
    f, satirlar, satir, genislik = c.font(ALTYAZI_FONT), [], [], 0
    bosluk = f.getlength(" ")
    for oge in kelimeler:
        w = f.getlength(oge[0])
        if satir and genislik + bosluk + w > ALTYAZI_GENISLIK - 60:
            satirlar.append(satir)
            satir, genislik = [], 0
        satir.append((oge, w))
        genislik += (bosluk if genislik else 0) + w
    satirlar.append(satir)
    return satirlar


def ingilizce_satirlar(metin_en, cumle_sayisi):
    """İngilizce metni Türkçe cümlelerle eşleştirir; cümle sayıları tutmazsa her cümlede metnin tamamı görünür."""
    if not metin_en:
        return [[] for _ in range(cumle_sayisi)]
    parcalar = re.split(r"(?<=[.!?])\s+", metin_en.strip())
    if len(parcalar) != cumle_sayisi:
        parcalar = [metin_en.strip()] * cumle_sayisi
    f = c.font(EN_FONT, kalin=False)
    sonuc = []
    for parca in parcalar:
        satirlar, satir = [], ""
        for kelime in parca.split():
            aday = (satir + " " + kelime).strip()
            if satir and f.getlength(aday) > ALTYAZI_GENISLIK - 60:
                satirlar.append(satir)
                satir = kelime
            else:
                satir = aday
        satirlar.append(satir)
        sonuc.append(satirlar)
    return sonuc


def altyazi(z, satirlar, t, en_satirlar=(), vurgu=c.MARKA_TURUNCU):
    f = c.font(ALTYAZI_FONT)
    bosluk = f.getlength(" ")
    x0 = 540 - ALTYAZI_GENISLIK / 2
    en_yukseklik = len(en_satirlar) * EN_SATIR + 14 if en_satirlar else 0
    yukseklik = len(satirlar) * SATIR + 50 + en_yukseklik
    katman = Image.new("RGBA", z.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(katman)
    d.rounded_rectangle((x0, ALTYAZI_UST, x0 + ALTYAZI_GENISLIK, ALTYAZI_UST + yukseklik), radius=10, fill=(0, 0, 0, 175))
    for i, satir in enumerate(satirlar):
        toplam = sum(w for _, w in satir) + bosluk * (len(satir) - 1)
        x, y = 540 - toplam / 2, ALTYAZI_UST + 25 + i * SATIR + SATIR / 2
        for (kelime, bas, son), w in satir:
            renk = vurgu if bas <= t < son else c.BEYAZ
            d.text((x, y), kelime, font=f, fill=renk, anchor="lm")
            x += w + bosluk
    y = ALTYAZI_UST + 25 + len(satirlar) * SATIR + 14 + EN_SATIR / 2
    for satir in en_satirlar:
        d.text((540, y), satir, font=c.font(EN_FONT, kalin=False), fill=(170, 178, 195), anchor="mm")
        y += EN_SATIR
    z.alpha_composite(katman)


# ---------------------------------------------------------------- ana akış

def logo_karti_karesi(logo, t, sure, alt_yazi=None):
    """Koyu zeminde Viteskop logosu: hafif yakınlaşarak belirir."""
    z = Image.new("RGBA", (c.W, c.H), (0, 0, 0, 255))  # logonun siyah zemini
    x = min(1.0, t / sure)
    olcek = 1.0 + 0.1 * (1 - x) ** 2
    resim = c.olcekle(logo, 0.8 * c.W / logo.width * olcek)
    gorunurluk = min(1.0, t / 0.5)
    resim.putalpha(resim.getchannel("A").point(lambda a: int(a * gorunurluk)))
    c.ortala_yapistir(z, resim, c.W / 2, 820)
    if alt_yazi and t > 0.3:
        y = max(1130, 820 + 0.8 * c.W / logo.width * logo.height / 2 + 110)  # kare logo daha uzun
        c.metin_ciz(z, alt_yazi[0], c.W / 2, y, 64, c.BEYAZ)
        c.metin_ciz(z, alt_yazi[1], c.W / 2, y + 90, 52, c.TURUNCU_MARKA)
    return z


def uret(senaryo_yolu, cikti_yolu):
    senaryo = json.load(open(senaryo_yolu, encoding="utf-8"))
    tema_ = tm.sec(senaryo)
    print(f"tema: {tema_['ad']}, müzik: {tema_['muzik'][0]}")
    gecici = tempfile.mkdtemp()
    konusma_basi = ACILIS + BASTA_BOSLUK
    ses_parcalari, plan, zaman, motorlar = [np.zeros(int(konusma_basi * SR))], [], konusma_basi, set()

    wavlar = [os.path.join(gecici, f"{i}.wav") for i in range(len(senaryo["sahneler"]))]
    print(f"{len(wavlar)} sahne seslendiriliyor…")
    motorlar.add(ses.seslendir_hepsi([sh["metin"] for sh in senaryo["sahneler"]], wavlar))

    for i, (sahne, wav) in enumerate(zip(senaryo["sahneler"], wavlar)):
        with wave.open(wav) as w:
            veri = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16) / 32768
        konusma = len(veri) / SR
        son = i == len(senaryo["sahneler"]) - 1
        bosluk = SONDA_BOSLUK if son else SAHNE_ARASI
        kz = kelime_zamanlari(sahne["metin"], konusma)
        plan.append({"tip": sahne["tip"], "veri": sahne, "bas": zaman, "konusma": konusma, "son": zaman + konusma + bosluk,
                     "kz": kz, "cumleler": [(cm[0][1], cm[-1][2], satirlara_bol(cm), en) for cm, en in
                                            zip(cumleler(kz), ingilizce_satirlar(sahne.get("metin_en"), len(cumleler(kz))))]})
        ses_parcalari += [veri, np.zeros(int(bosluk * SR))]
        zaman += konusma + bosluk
    plan[0]["bas"] = ACILIS
    ses_parcalari.append(np.zeros(int(KAPANIS_KARTI * SR)))

    konusma_izi = np.concatenate(ses_parcalari)
    toplam = len(konusma_izi) / SR
    karisim = np.clip(konusma_izi + 0.09 * tm.muzik(tema_, toplam)[:len(konusma_izi)], -1, 1)
    ses_yolu = os.path.join(gecici, "ses.wav")
    with wave.open(ses_yolu, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((karisim * 32767).astype(np.int16).tobytes())

    print("çizimler hazırlanıyor…")
    modul = sahne_modulu(senaryo_yolu)
    sahneler = {**ORTAK_SAHNELER, **modul.SAHNELER}
    tanimlar = {**ORTAK_ARKA_PLANLAR, **modul.ARKA_PLANLAR}
    eksik = {sh["tip"] for sh in senaryo["sahneler"]} - set(sahneler)
    if eksik:
        sys.exit(f"Bu sahne tipleri tanımlı değil: {', '.join(sorted(eksik))}")
    zeminler = {}
    for i, sh in enumerate(senaryo["sahneler"]):
        if sh["tip"] not in zeminler:
            zeminler[sh["tip"]] = arka_plan_yap(tanimlar.get(sh["tip"]), tema_, i)
    ortak, v = ortak_varliklar(), modul.hazirla()
    efekt = tm.Parcaciklar(tema_)
    rnd = random.Random(tema_["tohum"])
    kameralar = [rnd.choice(tm.KAMERA_HAREKETLERI) for _ in plan]
    gecisler = [rnd.choice(tm.GECISLER) for _ in range(len(plan) + 1)]
    onceki_katman, onceki_bolum, gecis_kaynak, gecis_bas = None, None, None, None
    marka_logo = c.logo(900)
    kare_sayisi = int(toplam * FPS)
    ffmpeg = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{c.W}x{c.H}",
         "-r", str(FPS), "-i", "-", "-i", ses_yolu, "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", cikti_yolu],
        stdin=subprocess.PIPE)

    for k in range(kare_sayisi):
        tg = k / FPS
        sahne = None
        if tg < ACILIS or tg >= plan[-1]["son"]:
            kapanis = tg >= plan[-1]["son"]
            t = tg - plan[-1]["son"] if kapanis else tg
            bolum = len(plan) if kapanis else -1
            katman = logo_karti_karesi(marka_logo, t, KAPANIS_KARTI if kapanis else ACILIS,
                                       ("Takip et,", "her gün yeni bir oto bilgisi!") if kapanis else None)
        else:
            sahne = next(s for s in plan if tg < s["son"])
            bolum = plan.index(sahne)
            st = tg - (sahne["bas"] if bolum else konusma_basi)  # konuşmaya göre zaman
            katman = zeminler[sahne["tip"]].copy()
            sahneler[sahne["tip"]](katman, st, Baglam(sahne["veri"], sahne["konusma"], sahne["kz"], v, ortak, tema_, senaryo["baslik"], senaryo))
            efekt.ciz(katman, tg)
            katman = tm.kamera(katman, (tg - sahne["bas"]) / max(0.1, sahne["son"] - sahne["bas"]), kameralar[bolum])
        if bolum != onceki_bolum:  # yeni bölüm: önceki bölümün son karesinden geçiş yap
            gecis_kaynak, gecis_bas = onceki_katman, tg
            onceki_bolum = bolum
        onceki_katman = katman
        if gecis_kaynak is not None and tg - gecis_bas < GECIS_SURESI:
            katman = tm.gecis(gecis_kaynak, katman, (tg - gecis_bas) / GECIS_SURESI, gecisler[bolum])
        z = katman.copy() if katman is onceki_katman else katman
        if sahne is not None:
            baslik(z, senaryo["baslik"], ortak, soru_goster=sahne["tip"] not in ("giris", "kapanis"), seri=senaryo.get("seri"),
                   vurgu=tema_["vurgu"], ilerleme=tg / toplam)
            aktif = [cm for cm in sahne["cumleler"] if cm[0] <= st + 0.05]
            if aktif and st < sahne["konusma"] + SAHNE_ARASI * 0.8:
                altyazi(z, aktif[-1][2], st, aktif[-1][3], vurgu=tema_["vurgu"])
        ffmpeg.stdin.write(z.convert("RGB").tobytes())
        if k % (FPS * 10) == 0:
            print(f"  {tg:5.1f}s / {toplam:.1f}s")

    ffmpeg.stdin.close()
    ffmpeg.wait()
    print(f"bitti: {cikti_yolu} ({toplam:.1f} sn, ses motoru: {', '.join(sorted(motorlar))})")


if __name__ == "__main__":
    yol = sys.argv[1]
    cikti = sys.argv[2] if len(sys.argv) > 2 else os.path.join("cikti", os.path.splitext(os.path.basename(yol))[0] + ".mp4")
    uret(yol, cikti)
