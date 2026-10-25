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
            kelime = (anahtarlar or [None] * adet)[i] if anahtarlar and i < len(anahtarlar) else None
            anlar.append(self.zaman(c.sadelestir(kelime), varsayilan) if kelime else varsayilan)
        return anlar


ORTAK_ARKA_PLANLAR = {}  # bütün sahneler temanın dünyasında geçer


def ortak_varliklar():
    return SimpleNamespace(
        logo_kucuk=c.logo_karti(230),
        yorum_balonu=c.konusma_balonu("…", boyut=110),
        soru_balonu=c.konusma_balonu("?", boyut=120),
    )


def _satirlar(kelimeler, boyut, genislik=900):
    f, satirlar, satir = c.font(boyut), [], []
    for k in kelimeler:
        if satir and f.getlength(" ".join(satir + [k])) > genislik:
            satirlar.append(satir)
            satir = []
        satir.append(k)
    return satirlar + [satir]


def _arac(tanim, w, teker_aci=0.0, yon=1):
    """Senaryodaki araba tanımı: {"ad": "...", "tip": "suv", "renk": [r, g, b]}"""
    tanim = tanim or {}
    renk = tuple(tanim.get("renk") or c.MAVI)
    return c.araba(w, renk, tanim.get("tip", "sedan"), teker_aci=teker_aci, yon=yon)


def sahne_giris(z, t, s):
    """Seri rozeti ve soru: ekranın ortasında büyük ve hareketli. Düzen başlığa göre değişir."""
    t += BASTA_BOSLUK  # sesten önceki boşlukta da çiz: soru videonun ilk karesinden belirmeye başlar
    soru = s.baslik.split()
    duzen = s.tema["tohum"] % 3
    vurgu = s.tema["vurgu"]
    rozet = c.seri_rozeti(s.senaryo.get("seri"))
    if rozet:
        olcek = c.pop(t, 0.0, 0.3)
        if olcek:
            c.ortala_yapistir(z, c.olcekle(rozet, olcek), 540, 440)
    boyut = 100 if len(s.baslik) < 24 else 84
    satirlar = _satirlar(soru, boyut)
    y0 = 720 - (len(satirlar) - 1) * boyut * 0.62
    if duzen == 0:  # koyu cam kart
        olcek = c.pop(t, 0.05)
        if olcek:
            yuk = len(satirlar) * boyut * 1.25 + 90
            c.ortala_yapistir(z, c.olcekle(c.kart(990, int(yuk), cerceve=vurgu + (255,)), olcek), 540, 720)
    elif duzen == 1:  # arkadan bir araba geçer
        x = -400 + (t / max(0.1, s.sure + BASTA_BOSLUK)) * 1900
        ar = _arac(s.senaryo.get("araba") or {"renk": list(vurgu), "tip": "sedan"}, 620, teker_aci=t * 400)
        c.ortala_yapistir(z, c.saydamlik(ar, 0.9), x, 1000 - ar.height / 2 + 10)
    sira = 0
    f = c.font(boyut)
    for i, satir in enumerate(satirlar):
        x = 540 - f.getlength(" ".join(satir)) / 2
        y = y0 + i * boyut * 1.25
        for n, kelime in enumerate(satir):
            w = f.getlength(kelime)
            son = i == len(satirlar) - 1 and n == len(satir) - 1
            t0 = 0.12 + sira * 0.14
            renk = vurgu if son else c.BEYAZ
            if duzen == 2:  # kelimeler yandan hızla kayarak gelir
                ilerleme = c.kayarak(t, t0, 0.35)
                if ilerleme:
                    c.metin_ciz(z, kelime, x + w / 2 + (1 - ilerleme) * 700, y, boyut, renk, kontur=c.KOYU, kontur_kalinlik=10)
            else:
                olcek = c.pop(t, t0, 0.3)
                if olcek:
                    c.metin_ciz(z, kelime, x + w / 2, y, max(8, int(boyut * olcek)), renk, kontur=c.KOYU,
                                kontur_kalinlik=0 if duzen == 0 else 10)
            x += w + f.getlength(" ")
            sira += 1


def sahne_bilgi(z, t, s):
    """Büyük bir yazı kartı: {"tip": "bilgi", "yazi": "...", "metin": "..."}."""
    satirlar = c.satirlara_sar(s.veri.get("yazi", ""), 92, 860)
    olcek = c.pop(t, 0.1)
    if not olcek:
        return
    yuk = len(satirlar) * 130 + 100
    c.ortala_yapistir(z, c.olcekle(c.kart(980, yuk, cerceve=s.tema["vurgu"] + (255,)), olcek), 540, 720)
    for i, satir in enumerate(satirlar):
        c.metin_ciz(z, satir, 540, 720 + (i - (len(satirlar) - 1) / 2) * 130, max(8, int(92 * olcek)),
                    s.tema["vurgu"] if i == 0 else c.BEYAZ)


def sahne_kiyas(z, t, s):
    """İki araba yan yana ve satır satır karşılaştırma.

    {"tip": "kiyas", "sol": {"ad": "Togg T10X", "tip": "suv", "renk": [..]}, "sag": {...},
     "satirlar": [{"ad": "Fiyat", "sol": "1,9 M TL", "sag": "1,6 M TL", "kazanan": "sag", "anahtar": "fiyat"}]}
    """
    vurgu = s.tema["vurgu"]
    sol, sag = s.veri.get("sol", {}), s.veri.get("sag", {})
    giris = c.kayarak(t, 0.0, 0.7)
    teker = (1 - giris) * 360
    a1 = _arac(sol, 380, teker_aci=teker, yon=1)
    a2 = _arac(sag, 380, teker_aci=teker, yon=-1)
    c.ortala_yapistir(z, a1, 240 - (1 - giris) * 600, 460)
    c.ortala_yapistir(z, a2, 840 + (1 - giris) * 600, 460)
    olcek = c.pop(t, 0.5, 0.3)
    if olcek:
        k = c.Kalem(130, 130)
        k.daire(65, 65, 62, fill=vurgu)
        k.daire(65, 65, 62, outline=c.BEYAZ, width=5)
        vs = k.bitir()
        c.metin_ciz(vs, "VS", 65, 66, 50, c.BEYAZ)
        c.ortala_yapistir(z, c.olcekle(vs, olcek), 540, 455)
    c.etiket(z, sol.get("ad", ""), 250, 590, boyut=38, olcek=c.pop(t, 0.6))
    c.etiket(z, sag.get("ad", ""), 830, 590, boyut=38, olcek=c.pop(t, 0.7))
    satirlar = s.veri.get("satirlar", [])[:5]
    anlar = s.sirali(len(satirlar), [r.get("anahtar") for r in satirlar], bas=0.18, son=0.82)
    for i, (satir, t0) in enumerate(zip(satirlar, anlar)):
        ilerleme = c.kayarak(t, t0, 0.35)
        if not ilerleme:
            continue
        y = 690 + i * 96 + (1 - ilerleme) * 40
        kart = c.saydamlik(c.kart(980, 82, r=24), ilerleme)
        c.ortala_yapistir(z, kart, 540, y)
        kazanan = satir.get("kazanan")
        for taraf, x in (("sol", 210), ("sag", 870)):
            deger = str(satir.get(taraf, ""))
            if kazanan == taraf:
                c.etiket(z, deger, x, y, boyut=38, zemin_rengi=vurgu + (255,), olcek=ilerleme)
            else:
                c.metin_ciz(z, deger, x, y, 38, c.ACIK_GRI if kazanan else c.BEYAZ)
        c.metin_ciz(z, satir.get("ad", ""), 540, y, 32, c.GRI, kalin=False)


def sahne_araba(z, t, s):
    """Araba soldan gelip ortada durur; istenirse parçalarını etiketlerle gösterir.

    {"tip": "araba", "araba": {"tip": "sedan", "renk": [..]}, "yazi": "...",
     "etiketler": [{"yazi": "Lastik", "x": 0.22, "y": 0.85, "anahtar": "lastik"}]}
    """
    tanim = s.veri.get("araba") or s.senaryo.get("araba") or {"renk": list(s.tema["vurgu"])}
    ilerleme = c.kayarak(t, 0.0, 1.1)
    yaylanma = 8 * math.sin(max(0.0, t - 1.1) * 12) * math.exp(-max(0.0, t - 1.1) * 4) if t > 1.1 else 0
    ar = _arac(tanim, 780, teker_aci=ilerleme * 540)
    x, y = -500 + ilerleme * 1040, 1005 - ar.height / 2 + yaylanma
    c.ortala_yapistir(z, ar, x, y)
    sol_ust = (x - ar.width / 2, y - ar.height / 2)
    if s.veri.get("yazi"):
        c.etiket(z, s.veri["yazi"], 540, 470, boyut=54, zemin_rengi=s.tema["vurgu"] + (255,), olcek=c.pop(t, 0.6))
    etiketler = s.veri.get("etiketler", [])[:4]
    anlar = s.sirali(len(etiketler), [e.get("anahtar") for e in etiketler], bas=0.3, son=0.8)
    for i, (e, t0) in enumerate(zip(etiketler, anlar)):
        olcek = c.pop(t, max(t0, 1.2))
        if not olcek:
            continue
        px, py = sol_ust[0] + e.get("x", 0.5) * ar.width, sol_ust[1] + e.get("y", 0.5) * ar.height
        ey = 620 + (i % 2) * 90
        d = ImageDraw.Draw(z)
        d.line([(px, py), (px, ey + 30)], fill=s.tema["vurgu"] + (255,), width=4)
        d.ellipse((px - 10, py - 10, px + 10, py + 10), fill=s.tema["vurgu"] + (255,), outline=c.BEYAZ + (255,), width=3)
        c.etiket(z, e.get("yazi", ""), max(160, min(920, px)), ey, boyut=40, olcek=olcek, cerceve=s.tema["vurgu"] + (255,))


def sahne_ikaz(z, t, s):
    """Gösterge paneli ve yanıp sönen ikaz lambası: {"tip": "ikaz", "ikon": "motor", "renk": "sari", "yazi": "..."}"""
    renk = c.IKAZ_RENKLERI.get(s.veri.get("renk", "sari"), c.KEHRIBAR)
    olcek = c.pop(t, 0.0, 0.4)
    if not olcek:
        return
    panel = c.kart(1000, 470, renk=(10, 12, 18, 240), cerceve=(60, 70, 90, 255), r=60)
    c.ortala_yapistir(z, c.olcekle(panel, olcek), 540, 740)
    if olcek < 1:
        return
    sol = c.gosterge(150, 0.25 + 0.05 * math.sin(t * 2), renk=c.MAVI, yazi="km/s")
    sag = c.gosterge(150, 0.35 + 0.08 * math.sin(t * 1.3 + 1), renk=c.MAVI, yazi="x1000")
    c.ortala_yapistir(z, sol, 215, 740)
    c.ortala_yapistir(z, sag, 865, 740)
    yanip = 0.5 + 0.5 * math.cos(max(0.0, t - 0.4) * 5) if t < s.sure * 0.7 else 1.0
    lamba = c.ikaz_lambasi(s.veri.get("ikon", "motor"), 260, renk, parlak=yanip)
    c.ortala_yapistir(z, c.olcekle(lamba, c.pop(t, 0.35) or 0.01), 540, 740)
    if s.veri.get("yazi"):
        c.etiket(z, s.veri["yazi"], 540, 1060, boyut=52, zemin_rengi=renk + (255,), renk=c.KOYU, olcek=c.pop(t, 0.8))


def sahne_liste(z, t, s):
    """Numaralı ipuçları: {"tip": "liste", "maddeler": ["...", "..."], "ikonlar": ["yag", null], "anahtarlar": [...]}
    ikonlar: parça adı (lastik, aku, yag_bidonu…) ya da ikaz simgesi (motor, fren…)."""
    vurgu = s.tema["vurgu"]
    maddeler = s.veri.get("maddeler", [])[:5]
    ikonlar = s.veri.get("ikonlar", [])
    anlar = s.sirali(len(maddeler), s.veri.get("anahtarlar"), bas=0.1, son=0.75)
    y = 380
    for i, (madde, t0) in enumerate(zip(maddeler, anlar)):
        satirlar = c.satirlara_sar(madde, 44, 680)
        yuk = 60 + len(satirlar) * 54
        ilerleme = c.kayarak(t, t0, 0.35)
        if ilerleme:
            x = 540 + (1 - ilerleme) * 900
            c.ortala_yapistir(z, c.kart(980, yuk, r=30), x, y + yuk / 2)
            k = c.Kalem(84, 84)
            k.daire(42, 42, 40, fill=vurgu)
            numara = k.bitir()
            c.metin_ciz(numara, str(i + 1), 42, 43, 46, c.BEYAZ)
            c.ortala_yapistir(z, numara, x - 420, y + yuk / 2)
            for j, satir in enumerate(satirlar):
                ImageDraw.Draw(z).text((x - 355, y + yuk / 2 + (j - (len(satirlar) - 1) / 2) * 54), satir,
                                       font=c.font(44), fill=c.BEYAZ, anchor="lm")
            ikon = ikonlar[i] if i < len(ikonlar) else None
            if ikon:
                resim = c.ikaz_lambasi(ikon, 90, vurgu) if ikon in c_IKAZLAR else c.parca(ikon, 96)
                c.ortala_yapistir(z, resim, x + 420, y + yuk / 2)
        y += yuk + 22


c_IKAZLAR = {"motor", "yag", "aku", "sicaklik", "fren", "lastik_basinci", "abs", "hava_yastigi"}  # liste ikonu: ikaz simgesi


_parca_onbellek = {}


def sahne_parca(z, t, s):
    """Büyük parça çizimi ve notlar: {"tip": "parca", "parca": "fren_diski", "yazi": "Fren diski", "notlar": ["...", "..."]}"""
    ad = s.veri.get("parca", "lastik")
    olcek = c.pop(t, 0.05, 0.45)
    if not olcek:
        return
    if ad in ("lastik", "fren_diski"):  # dönenler
        aci = int(t * 40) % 360 // 4 * 4
        if (ad, aci) not in _parca_onbellek:
            if len(_parca_onbellek) > 200:
                _parca_onbellek.clear()
            _parca_onbellek[(ad, aci)] = c.parca(ad, 480, aci=aci)
        resim = _parca_onbellek[(ad, aci)]
    else:
        if (ad, None) not in _parca_onbellek:
            _parca_onbellek[(ad, None)] = c.parca(ad, 480)
        resim = _parca_onbellek[(ad, None)]
    c.ortala_yapistir(z, c.olcekle(resim, olcek), 540, 650 + 14 * math.sin(t * 1.6))
    if s.veri.get("yazi"):
        c.etiket(z, s.veri["yazi"], 540, 960, boyut=58, zemin_rengi=s.tema["vurgu"] + (255,), olcek=c.pop(t, 0.4))
    notlar = s.veri.get("notlar", [])[:3]
    anlar = s.sirali(len(notlar), s.veri.get("anahtarlar"), bas=0.3, son=0.75)
    for i, (n, t0) in enumerate(zip(notlar, anlar)):
        x, y = [(170, 400), (910, 560), (170, 860)][i]
        c.etiket(z, n, x, y, boyut=36, olcek=c.pop(t, t0), cerceve=s.tema["vurgu"] + (255,))


def sahne_gosterge(z, t, s):
    """Gösterge iğnesi bir değere çıkar: {"tip": "gosterge", "deger": 0.7, "yazi": "10.000 km", "alt": "yağ değişimi"}"""
    olcek = c.pop(t, 0.0, 0.4)
    if not olcek:
        return
    hedef = float(s.veri.get("deger", 0.7))
    x = c.kayarak(t, 0.3, 1.4)
    deger = hedef * x + 0.04 * math.sin(t * 9) * (1 - x)
    resim = c.gosterge(320, deger, renk=s.tema["vurgu"], yazi=s.veri.get("yazi") if x > 0.6 else None, alt_yazi=s.veri.get("alt"))
    c.ortala_yapistir(z, c.olcekle(resim, olcek), 540, 700)


def sahne_uyari(z, t, s):
    """Güvenlik uyarısı: {"tip": "uyari", "yazi": "Fren işini ustaya bırak!"}"""
    vurgu = c.KEHRIBAR
    olcek = c.pop(t, 0.0, 0.4)
    if olcek:
        nabiz = 1 + 0.05 * math.sin(t * 6)
        k = c.Kalem(360, 320)
        k.cokgen([(180, 10), (350, 305), (10, 305)], fill=vurgu)
        k.cokgen([(180, 50), (312, 282), (48, 282)], fill=c.KOYU)
        k.kutu((164, 110, 196, 220), fill=vurgu, r=12)
        k.daire(180, 250, 18, fill=vurgu)
        c.ortala_yapistir(z, c.olcekle(k.bitir(), olcek * nabiz), 540, 560)
    satirlar = c.satirlara_sar(s.veri.get("yazi", ""), 60, 820)
    olcek = c.pop(t, 0.4)
    if olcek:
        yuk = len(satirlar) * 80 + 70
        c.ortala_yapistir(z, c.olcekle(c.kart(960, yuk, cerceve=vurgu + (255,)), olcek), 540, 900)
        for i, satir in enumerate(satirlar):
            c.metin_ciz(z, satir, 540, 900 + (i - (len(satirlar) - 1) / 2) * 80, max(8, int(60 * olcek)), c.BEYAZ)


def sahne_kapanis(z, t, s):
    """Serinin sorusu (ya da senaryodaki "soru") ve yorum/kaydet çağrısı."""
    vurgu = s.tema["vurgu"]
    seri = c.SERILER.get(s.senaryo.get("seri"), {})
    soru = s.veri.get("soru") or s.senaryo.get("soru") or seri.get("soru") or "Sen ne düşünüyorsun?"
    olcek = c.pop(t, 0.1, 0.5)
    if olcek:
        c.ortala_yapistir(z, c.olcekle(s.ortak.yorum_balonu, olcek * 1.3), 540, 470 + 10 * math.sin(t * 2))
    satirlar = c.satirlara_sar(soru, 80, 900)
    for i, satir in enumerate(satirlar):
        c.metin_ciz(z, satir, 540, 760 + i * 100, max(8, int(80 * c.pop(t, 0.3 + i * 0.15))), c.BEYAZ,
                    kontur=c.KOYU, kontur_kalinlik=8)
    c.etiket(z, "Yorumlara yaz!", 540, 980, boyut=54, zemin_rengi=vurgu + (255,), olcek=c.pop(t, s.zaman("yorum", s.sure * 0.5)))
    c.etiket(z, "Kaydet, lazım olur", 540, 1090, boyut=44, olcek=c.pop(t, s.zaman("kaydet", s.sure * 0.7)), cerceve=vurgu + (255,))


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

def baslik(z, metin, ortak, soru_goster=True):
    c.ortala_yapistir(z, ortak.logo_kucuk, 540, 100)
    if soru_goster:
        c.etiket(z, metin, 540, 240, boyut=60 if len(metin) < 22 else 48)


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
    d.rounded_rectangle((x0, ALTYAZI_UST, x0 + ALTYAZI_GENISLIK, ALTYAZI_UST + yukseklik), radius=36, fill=c.KOYU + (225,))
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
            baslik(z, senaryo["baslik"], ortak, soru_goster=sahne["tip"] != "giris")
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
