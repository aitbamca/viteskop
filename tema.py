"""Videoya kimlik veren tema motoru: dünya (arka plan ve zemin), uçuşan efektler, kamera hareketi,
sahne geçişleri ve müzik. Aynı tema bile her videoda başlığa göre farklı çizilir (rastgelelik
başlıktan türetilir, yani aynı senaryo her üretimde aynı görünür).

Senaryoda "tema": "garaj" gibi seçilir; yoksa serinin teması, o da yoksa başlıktan tahmin edilir.
Senaryoda "seri" varsa vurgu rengi serinin rengi olur (Kafa Kafaya kırmızı, Bakım Saati yeşil…).
"""
import math
import random
import zlib

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import cizim as c

W, H = c.W, c.H
ZEMIN_UST = 1010  # zeminin ortalama başladığı yükseklik: çizimler bunun üstünde "durur"

# gok: (üst, alt) renk · zemin: zemin çizici · zemin_renk: katmanlar (uzaktan yakına)
# parcacik: uçuşan efekt · vurgu: altyazıda okunan kelimenin rengi · muzik: enstrüman, tempo, ton
TEMALAR = {
    "garaj": {"gok": ((34, 38, 50), (52, 58, 74)), "zemin": "garaj",
              "zemin_renk": [(44, 50, 64), (70, 76, 90), (58, 63, 76)], "parcacik": "toz",
              "vurgu": c.TURUNCU_MARKA, "muzik": ("synth", 102, 2)},
    "showroom": {"gok": ((10, 12, 20), (30, 34, 48)), "zemin": "showroom",
                 "zemin_renk": [(26, 30, 42), (40, 46, 62), (18, 20, 28)], "parcacik": "isilti",
                 "vurgu": c.KIRMIZI, "muzik": ("synth", 110, 9)},
    "otoyol": {"gok": ((42, 30, 84), (250, 130, 80)), "zemin": "otoyol",
               "zemin_renk": [(60, 40, 90), (46, 48, 58), (34, 36, 44)], "parcacik": "far",
               "vurgu": (255, 140, 60), "muzik": ("synth", 116, 5)},
    "gece_sehir": {"gok": ((8, 12, 30), (40, 34, 80)), "zemin": "gece_sehir",
                   "zemin_renk": [(26, 30, 54), (36, 40, 66), (22, 24, 34)], "parcacik": "yagmur",
                   "vurgu": (90, 170, 255), "muzik": ("pad", 92, 7)},
    "gosterge": {"gok": ((6, 10, 18), (16, 26, 44)), "zemin": "gosterge",
                 "zemin_renk": [(20, 30, 50), (30, 44, 70), (14, 20, 34)], "parcacik": "hud",
                 "vurgu": c.KEHRIBAR, "muzik": ("pad", 96, 0)},
}


def tohum(metin):
    return zlib.crc32(metin.encode("utf-8"))


# Senaryoda tema yazılmamışsa (ve seri yoksa) konudaki kelimelerden tahmin edilir.
ANAHTAR_KELIMELER = [
    ("gosterge", ["ikaz", "lamba", "uyarı ışığı", "gösterge", "arıza", "sensör", "beyin", "elektronik"]),
    ("showroom", [" vs ", "kıyas", "karşılaştır", "hangisi", "fiyat", "yeni model", "donanım"]),
    ("otoyol", ["yol", "uzun yol", "yakıt", "tüketim", "menzil", "otoyol", "hız", "seyahat"]),
    ("gece_sehir", ["gece", "far", "yağmur", "sis", "şehir içi", "trafik", "park"]),
    ("garaj", ["yağ", "bakım", "filtre", "balata", "fren", "lastik", "akü", "buji", "parça", "usta", "sanayi"]),
]


def tahmin(senaryo):
    metin = " " + (senaryo["baslik"] + " " + " ".join(sh.get("metin", "") for sh in senaryo["sahneler"])).lower() + " "
    puan = {ad: sum(metin.count(k) for k in kelimeler) for ad, kelimeler in ANAHTAR_KELIMELER}
    baslik = " " + senaryo["baslik"].lower() + " "
    for ad, kelimeler in ANAHTAR_KELIMELER:  # başlıktaki eşleşme çok daha önemli
        puan[ad] += 5 * sum(baslik.count(k) for k in kelimeler)
    en_iyi = max(puan, key=lambda ad: puan[ad])
    return en_iyi if puan[en_iyi] else sorted(TEMALAR)[tohum(senaryo["baslik"]) % len(TEMALAR)]


def sec(senaryo):
    seri = c.SERILER.get(senaryo.get("seri"))
    ad = senaryo.get("tema")
    if ad not in TEMALAR:
        ad = seri["tema"] if seri else tahmin(senaryo)
    t = dict(TEMALAR[ad])
    t["ad"] = ad
    t["tohum"] = tohum(senaryo["baslik"])
    if seri:
        t["vurgu"] = seri["renk"]
    return t


def renk_karistir_(a, b, t):
    return c.renk_karistir(a[:3], b[:3], t)


def koyu(renk, k):
    return tuple(max(0, min(255, int(v * k))) for v in renk[:3])


# ---------------------------------------------------------------- dünya (arka plan + zemin)

def _isik_huzmesi(k, x, ust, alt_y, genislik, renk, alfa):
    k.cokgen([(x - 30, ust), (x + 30, ust), (x + genislik, alt_y), (x - genislik, alt_y)], fill=renk + (alfa,))


def ortam(tema, tohum_eki=0, gok=None, zemin=True):
    """Temanın dünyası. Her sahne için tohum_eki farklı verilir (aynı temada küçük farklar)."""
    rnd = random.Random(tema["tohum"] * 31 + tohum_eki)
    ust, alt = gok or tema["gok"]
    img = c.gradyan(ust, alt)
    k = c.Kalem(W, H)
    isik = c.Kalem(W, H)  # yarı saydam ışıklar ayrı katmanda: alttakini silmeden üstüne biner
    ust_isik = c.Kalem(W, H)
    aletler = []  # zemine sonradan yapıştırılacak hazır çizimler
    tur, renk = tema["zemin"], tema["zemin_renk"]
    vurgu = tema["vurgu"]

    if tur == "garaj":
        for x in range(0, W, 270):  # duvar panelleri
            k.kutu((x + 6, 300, x + 264, ZEMIN_UST - 20), fill=koyu(renk[0], 1.12), r=6)
        px = rnd.choice([60, 560])  # delikli alet panosu
        k.kutu((px, 380, px + 460, 760), fill=(58, 64, 80), r=10)
        for yy in range(400, 750, 28):
            for xx in range(px + 20, px + 450, 28):
                k.daire(xx, yy, 3, fill=(40, 44, 56))
        for i, ad in enumerate(rnd.sample(["anahtar", "anahtar", "buji", "silecek"], 3)):
            aletler.append((c.saydamlik(c.parca(ad, 150, aci=rnd.uniform(0, 360)), 0.6), (int(px + 20 + i * 145), 480)))
        k.kutu((-10, ZEMIN_UST - 30, W + 10, ZEMIN_UST), fill=koyu(vurgu, 0.55))  # şerit
        for x in range(-40, W, 80):
            k.cokgen([(x, ZEMIN_UST - 30), (x + 40, ZEMIN_UST - 30), (x + 70, ZEMIN_UST), (x + 30, ZEMIN_UST)], fill=(30, 32, 40))
        k.kutu((-10, ZEMIN_UST, W + 10, H), fill=renk[1])  # beton zemin
        for _ in range(26):
            x, y = rnd.uniform(0, W), rnd.uniform(ZEMIN_UST + 40, H)
            isik.elips((x - rnd.uniform(30, 90), y - 8, x + rnd.uniform(30, 90), y + 8), fill=koyu(renk[1], 0.88) + (140,))
        for x in range(120, W, 280):  # tavan lambaları
            k.kutu((x - 70, 120, x + 70, 136), fill=(235, 240, 250), r=6)
            _isik_huzmesi(ust_isik, x, 136, ZEMIN_UST, 320, (255, 250, 230), 16)
    elif tur == "showroom":
        for x in (200, 540, 880):  # spot ışıkları
            _isik_huzmesi(ust_isik, x, 0, ZEMIN_UST + 80, 300, (255, 255, 255), 18)
            k.kutu((x - 40, 0, x + 40, 30), fill=(60, 64, 76), r=8)
        for i in range(7):  # arka duvarda ince ışık çizgileri
            y = 300 + i * 90
            isik.cizgi([(0, y), (W, y)], fill=koyu(vurgu, 0.7) + (70,), width=2)
        k.kutu((-10, ZEMIN_UST, W + 10, H), fill=renk[2])  # parlak zemin
        k.cizgi([(0, ZEMIN_UST), (W, ZEMIN_UST)], fill=vurgu + (200,), width=5)
        for x in (290, 790):  # kaide
            k.elips((x - 250, ZEMIN_UST + 10, x + 250, ZEMIN_UST + 80), fill=(40, 44, 58))
            k.elips((x - 250, ZEMIN_UST, x + 250, ZEMIN_UST + 60), fill=(56, 60, 76))
            k.elips((x - 250, ZEMIN_UST, x + 250, ZEMIN_UST + 60), outline=vurgu + (160,), width=3)
    elif tur == "otoyol":
        gx, gy = rnd.uniform(300, 780), ZEMIN_UST - 120
        k.daire(gx, gy, 170, fill=(255, 200, 120, 80))
        k.daire(gx, gy, 110, fill=(255, 210, 140))
        for j, taban in enumerate((ZEMIN_UST - 160, ZEMIN_UST - 70)):  # dağlar
            noktalar = [(-40, ZEMIN_UST)]
            x = -40
            while x < W + 80:
                noktalar.append((x, taban - rnd.uniform(40, 220) * (1 - j * 0.4)))
                x += rnd.uniform(90, 200)
            noktalar.append((W + 80, ZEMIN_UST))
            k.cokgen(noktalar, fill=koyu(renk[0], 0.9 - j * 0.3))
        k.kutu((-10, ZEMIN_UST, W + 10, H), fill=renk[1])  # yol
        k.cokgen([(0, ZEMIN_UST), (W, ZEMIN_UST), (W, ZEMIN_UST + 20), (0, ZEMIN_UST + 20)], fill=(120, 124, 136))
        for i in range(8):  # perspektif şerit çizgileri
            y = ZEMIN_UST + 60 + i * i * 14
            g = 8 + i * 6
            k.kutu((W / 2 - g, y, W / 2 + g, y + 10 + i * 4), fill=(255, 214, 90))
        k.cokgen([(0, ZEMIN_UST + 40), (60, ZEMIN_UST + 40), (-200, H), (-260, H)], fill=(230, 232, 238))
        k.cokgen([(W - 60, ZEMIN_UST + 40), (W, ZEMIN_UST + 40), (W + 260, H), (W + 200, H)], fill=(230, 232, 238))
    elif tur == "gece_sehir":
        for _ in range(40):
            k.daire(rnd.uniform(0, W), rnd.uniform(0, 600), rnd.uniform(1, 3), fill=(255, 255, 255, rnd.randint(80, 200)))
        x = -20
        while x < W:  # binalar
            g, b = rnd.uniform(100, 190), rnd.uniform(300, 700)
            k.kutu((x, ZEMIN_UST - b, x + g, ZEMIN_UST + 10), fill=renk[rnd.randint(0, 1)])
            for wy in range(int(ZEMIN_UST - b + 30), int(ZEMIN_UST - 20), 48):
                for wx in range(int(x + 16), int(x + g - 26), 36):
                    if rnd.random() < 0.45:
                        k.kutu((wx, wy, wx + 18, wy + 24), fill=rnd.choice([(255, 214, 120), (140, 200, 255), (255, 240, 200)]), r=2)
            x += g + rnd.uniform(6, 20)
        k.kutu((-10, ZEMIN_UST + 10, W + 10, H), fill=renk[2])  # ıslak asfalt
        for _ in range(30):  # yansımalar
            x = rnd.uniform(0, W)
            isik.kutu((x, ZEMIN_UST + rnd.uniform(40, 500), x + rnd.uniform(6, 16), ZEMIN_UST + rnd.uniform(520, 900)),
                      fill=rnd.choice([(255, 214, 120), (140, 200, 255)]) + (40,))
    elif tur == "gosterge":
        for i in range(14):  # HUD ızgarası
            ust_isik.cizgi([(0, 240 + i * 120), (W, 240 + i * 120)], fill=(70, 110, 170, 45), width=2)
            ust_isik.cizgi([(i * 90, 0), (i * 90, H)], fill=(70, 110, 170, 35), width=2)
        k.daire(W / 2, 760, 520, fill=renk_karistir_(tema["gok"][1], vurgu, 0.06))  # parıltı
        k.daire(W / 2, 760, 360, fill=renk_karistir_(tema["gok"][1], vurgu, 0.12))
        k.kutu((-10, ZEMIN_UST + 60, W + 10, H), fill=renk[2])  # torpido
        k.cizgi([(0, ZEMIN_UST + 60), (W, ZEMIN_UST + 60)], fill=(60, 80, 120), width=4)
    img.alpha_composite(k.bitir())
    for resim, yer in aletler:
        img.alpha_composite(resim, yer)
    img.alpha_composite(isik.bitir())
    img.alpha_composite(ust_isik.bitir())
    if tur in ("showroom", "gosterge", "gece_sehir"):
        img = img.filter(ImageFilter.GaussianBlur(1.2))  # derinlik: arka plan hafif bulanık
    return img


# ---------------------------------------------------------------- uçuşan efektler

class Parcaciklar:
    def __init__(self, tema, sayi=None):
        self.tur = tema["parcacik"]
        self.vurgu = tema["vurgu"]
        rnd = random.Random(tema["tohum"])
        sayi = sayi or {"toz": 34, "isilti": 22, "far": 10, "yagmur": 70, "hud": 26}.get(self.tur, 20)
        self.p = [(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(0.6, 1.4), rnd.uniform(0, 6.3)) for _ in range(sayi)]

    def ciz(self, z, t):
        d = ImageDraw.Draw(z)
        tur = self.tur
        for x0, y0, hiz, faz in self.p:
            if tur == "toz":
                x = (x0 + t * 14 * hiz) % W
                y = (y0 - t * 9 * hiz) % H
                parlak = 0.5 + 0.5 * math.sin(t * 2 * hiz + faz)
                r = 2 + 2.5 * hiz
                d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 245, 220, int(50 + 90 * parlak)))
            elif tur == "isilti":
                x, y = x0, y0 * 0.55
                parlak = max(0.0, math.sin(t * 2.2 * hiz + faz))
                r = (2 + 4 * hiz) * parlak
                if r > 0.5:
                    d.line([(x - r * 2.5, y), (x + r * 2.5, y)], fill=(255, 255, 255, int(200 * parlak)), width=3)
                    d.line([(x, y - r * 2.5), (x, y + r * 2.5)], fill=(255, 255, 255, int(200 * parlak)), width=3)
            elif tur == "far":  # uzaktan geçen far izleri
                y = ZEMIN_UST - 40 + (y0 % 60)
                x = (x0 + t * 420 * hiz) % (W + 400) - 200
                renk = (255, 240, 200) if hiz > 1 else (255, 70, 60)
                d.line([(x - 120 * hiz, y), (x, y)], fill=renk + (150,), width=4)
            elif tur == "yagmur":
                y = (y0 + t * 900 * hiz) % (H + 60) - 30
                x = (x0 - t * 120 * hiz) % W
                d.line([(x, y), (x - 6, y + 26)], fill=(180, 210, 255, 110), width=2)
            elif tur == "hud":
                x = x0
                y = (y0 - t * 30 * hiz) % H
                a = int(60 + 80 * (0.5 + 0.5 * math.sin(t * 3 * hiz + faz)))
                d.rectangle((x - 3, y - 3, x + 3, y + 3), fill=self.vurgu + (a,))


# ---------------------------------------------------------------- kamera ve geçişler

KAMERA_HAREKETLERI = ["yakinlas", "uzaklas", "sola", "saga", "yukari"]
GECISLER = ["kaydir", "daire", "perde", "yakinlas"]


def kamera(z, x, hareket, miktar=0.07):
    """x: sahnenin ilerlemesi (0-1). Sahne katmanına yavaş yakınlaşma ya da kayma uygular."""
    x = max(0.0, min(1.0, x))
    yumusak = x * x * (3 - 2 * x)
    if hareket == "yakinlas":
        s, ox, oy = 1 + miktar * yumusak, 0.5, 0.45
    elif hareket == "uzaklas":
        s, ox, oy = 1 + miktar * (1 - yumusak), 0.5, 0.45
    else:
        s = 1 + miktar
        ox = {"sola": 1 - yumusak, "saga": yumusak}.get(hareket, 0.5)
        oy = (1 - yumusak) if hareket == "yukari" else 0.45
    gw, gh = W / s, H / s
    x0, y0 = (W - gw) * ox, (H - gh) * oy
    return z.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + gw, y0 + gh))


_maske_onbellek = {}


def _daire_maskesi(r):
    anahtar = int(r / 8)
    if anahtar not in _maske_onbellek:
        m = Image.new("L", (W, H), 0)
        ImageDraw.Draw(m).ellipse((W / 2 - r, H * 0.45 - r, W / 2 + r, H * 0.45 + r), fill=255)
        _maske_onbellek[anahtar] = m.filter(ImageFilter.GaussianBlur(6))
        if len(_maske_onbellek) > 400:
            _maske_onbellek.clear()
    return _maske_onbellek[anahtar]


def gecis(onceki, yeni, x, stil):
    """x 0→1: önceki sahneden yenisine geçiş."""
    x = max(0.0, min(1.0, x))
    e = 1 - (1 - x) ** 3
    if stil == "kaydir":
        kayma = int(W * e)
        sonuc = Image.new("RGBA", (W, H))
        sonuc.paste(onceki.crop((kayma, 0, W, H)), (0, 0))
        if kayma:
            sonuc.paste(yeni.crop((0, 0, kayma, H)), (W - kayma, 0))
        return sonuc
    if stil == "daire":
        return Image.composite(yeni, onceki, _daire_maskesi(e * math.hypot(W, H) * 0.62))
    if stil == "perde":
        sinir = int(H * e)
        sonuc = onceki.copy()
        sonuc.paste(yeni.crop((0, 0, W, sinir)), (0, 0))
        if 4 < sinir < H - 4:
            ImageDraw.Draw(sonuc).rectangle((0, sinir - 6, W, sinir + 6), fill=(255, 255, 255, 230))
        return sonuc
    # yakinlas: önceki büyüyüp kaybolur, yenisi belirir
    buyuk = kamera(onceki, 1.0, "yakinlas", miktar=0.25 * e)
    return Image.blend(buyuk, yeni, e)


# ---------------------------------------------------------------- müzik

AKOR_DIZILERI = [
    [(0, 4, 7), (7, 11, 14), (9, 12, 16), (5, 9, 12)],    # I V vi IV
    [(0, 4, 7), (9, 12, 16), (5, 9, 12), (7, 11, 14)],    # I vi IV V
    [(9, 12, 16), (5, 9, 12), (0, 4, 7), (7, 11, 14)],    # vi IV I V
    [(0, 4, 7), (5, 9, 12), (0, 4, 7), (7, 11, 14)],      # I IV I V
]
DESENLER = [[0, 1, 2, 1, 0, 1, 2, 1], [0, 1, 2, 3, 2, 1, 2, 1], [0, 2, 1, 2, 0, 2, 1, 3], [2, 1, 0, 1, 2, 3, 2, 1]]


def _nota(enstruman, f, sure, sr):
    t = np.arange(int(sr * sure)) / sr
    if enstruman == "marimba":
        return np.exp(-t * 6) * np.sin(2 * np.pi * f * t) + 0.35 * np.exp(-t * 18) * np.sin(2 * np.pi * f * 4 * t)
    if enstruman == "kalimba":
        return np.exp(-t * 3.2) * np.sin(2 * np.pi * f * t) + 0.25 * np.exp(-t * 14) * np.sin(2 * np.pi * f * 5.4 * t)
    if enstruman == "ukulele":
        return sum(a * np.exp(-t * (4 + 3 * i)) * np.sin(2 * np.pi * f * (i + 1) * t) for i, a in enumerate([1, 0.5, 0.3, 0.18]))
    if enstruman == "pad":
        zarf = np.minimum(1, t / 0.4) * np.exp(-t * 0.9)
        return zarf * (np.sin(2 * np.pi * f * t) + 0.7 * np.sin(2 * np.pi * f * 1.004 * t) + 0.3 * np.sin(2 * np.pi * f * 2 * t))
    if enstruman == "synth":  # parlak, kısa synth vuruşu (testere dişine yakın harmonikler)
        return np.exp(-t * 7) * sum(np.sin(2 * np.pi * f * n * t) / n for n in range(1, 7))
    if enstruman == "bas":
        return np.exp(-t * 5) * (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t))
    if enstruman == "davul":  # yumuşak bas davul: hızla düşen frekans
        return np.exp(-t * 18) * np.sin(2 * np.pi * (50 + 90 * np.exp(-t * 30)) * t)
    return np.exp(-t * 4.5) * (np.sin(2 * np.pi * f * t) + 0.25 * np.sin(4 * np.pi * f * t))  # müzik kutusu


def muzik(tema, sure, sr=44100):
    """Temaya göre enstrüman, tempo ve ton; başlığa göre akor dizisi ve desen. Telifsiz."""
    enstruman, tempo, ton = tema["muzik"]
    rnd = random.Random(tema["tohum"])
    akorlar, desen = rnd.choice(AKOR_DIZILERI), rnd.choice(DESENLER)
    tempo += rnd.randint(-6, 6)
    n = int(sure * sr)
    iz = np.zeros(n + sr * 3)
    sekizlik = 60 / tempo / 2
    kok = 60 + ton

    def midi_f(m):
        return 440 * 2 ** ((m - 69) / 12)

    i = 0
    while i * sekizlik < sure:
        akor = akorlar[(i // 8) % 4]
        bas = int(i * sekizlik * sr)
        if enstruman == "pad":
            if i % 8 == 0:
                parca = sum(_nota("pad", midi_f(kok + a - 12), sekizlik * 8.5, sr) for a in akor) * 0.35
                iz[bas:bas + len(parca)] += parca
            if i % 2 == 0:
                parca = _nota("muzik_kutusu", midi_f(kok + 12 + akor[desen[i % 8] % 3]), 1.2, sr) * 0.35
                iz[bas:bas + len(parca)] += parca
        else:
            if enstruman == "synth":  # ritim: her vuruşta davul, her ölçü başında bas
                if i % 2 == 0:
                    davul = _nota("davul", 0, 0.4, sr) * 0.55
                    iz[bas:bas + len(davul)] += davul
                if i % 4 == 0:
                    basnota = _nota("bas", midi_f(kok - 24 + akor[0]), 0.9, sr) * 0.5
                    iz[bas:bas + len(basnota)] += basnota
            nota_ = akor[desen[i % 8] % 3] + (12 if desen[i % 8] == 3 else 0)
            parca = _nota(enstruman, midi_f(kok + 12 + nota_), 1.2, sr) * 0.5
            if i % 8 == 0:
                parca = parca + _nota(enstruman, midi_f(kok - 12 + akor[0]), 1.2, sr) * 0.6
            iz[bas:bas + len(parca)] += parca
        i += 1
    iz = iz[:n]
    iz /= max(1e-6, np.max(np.abs(iz)))
    kararma = min(n, int(1.5 * sr))
    iz[-kararma:] *= np.linspace(1, 0, kararma)
    return iz
