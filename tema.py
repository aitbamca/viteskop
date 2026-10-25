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
    "garaj": {"gok": ((10, 12, 16), (22, 25, 32)), "zemin": "garaj", "zemin_renk": [], "parcacik": "yok",
              "vurgu": c.TURUNCU_MARKA, "muzik": ("nabiz", 92, 2)},
    "showroom": {"gok": ((8, 9, 13), (20, 22, 30)), "zemin": "showroom", "zemin_renk": [], "parcacik": "yok",
                 "vurgu": c.KIRMIZI, "muzik": ("nabiz", 100, 9)},
    "otoyol": {"gok": ((10, 11, 18), (26, 24, 36)), "zemin": "otoyol", "zemin_renk": [], "parcacik": "yok",
               "vurgu": c.TURUNCU_MARKA, "muzik": ("nabiz", 104, 5)},
    "gece_sehir": {"gok": ((6, 8, 16), (18, 22, 36)), "zemin": "gece_sehir", "zemin_renk": [], "parcacik": "yok",
                   "vurgu": (90, 170, 255), "muzik": ("pad", 84, 7)},
    "gosterge": {"gok": ((6, 8, 12), (16, 20, 28)), "zemin": "gosterge", "zemin_renk": [], "parcacik": "yok",
                 "vurgu": c.KEHRIBAR, "muzik": ("pad", 88, 0)},
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

def _filigran(tema, rnd):
    """Temaya göre büyük, soluk teknik çizim (arka planda derinlik için)."""
    tur = tema["zemin"]
    soluk = (232, 236, 243)
    if tur == "showroom":
        return c.saydamlik(c.araba_cizgi(1500, rnd.choice(["sedan", "suv"]), renk=soluk), 0.07), (rnd.choice([-260, -120]), 1180)
    if tur == "garaj":
        return c.saydamlik(c.parca_cizgi(rnd.choice(["lastik", "fren_diski"]), 1100, aci=rnd.uniform(0, 60), renk=soluk), 0.06), (rnd.choice([-380, 360]), 640)
    if tur == "gosterge":
        return c.saydamlik(c.gosterge(560, 0.0, renk=(60, 64, 76)), 0.07), (-20, 380)
    return None, None


def ortam(tema, tohum_eki=0, gok=None, zemin=True):
    """Ciddi, sade stüdyo zemini: koyu gradyan, ince ızgara, temaya göre soluk teknik çizim, kenar kararması."""
    rnd = random.Random(tema["tohum"] * 31 + tohum_eki)
    ust, alt = gok or tema["gok"]
    img = c.gradyan(ust, alt)
    k = c.Kalem(W, H)
    tur = tema["zemin"]
    for x in range(0, W + 1, 60):  # ızgara
        k.cizgi([(x, 0), (x, H)], fill=(255, 255, 255, 9), width=1)
    for y in range(0, H + 1, 60):
        k.cizgi([(0, y), (W, y)], fill=(255, 255, 255, 9), width=1)
    if tur == "otoyol":  # perspektif yol çizgileri
        ufuk = 760
        for x in (-900, -300, 300, 900):
            k.cizgi([(W / 2, ufuk), (W / 2 + x * 1.6, H)], fill=(255, 255, 255, 22), width=2)
        for i in range(10):
            y = ufuk + 20 + i * i * 9
            k.cizgi([(W / 2 - 2 - i, y), (W / 2 + 2 + i, y + 10 + i * 3)], fill=tema["vurgu"] + (60,), width=4 + i)
    elif tur == "gece_sehir":  # ince çizgili şehir silüeti
        x, onceki = -10, 1150
        noktalar = [(x, onceki)]
        while x < W + 20:
            g, y = rnd.uniform(70, 160), 1150 - rnd.uniform(120, 420)
            noktalar += [(x, y), (x + g, y)]
            x += g
        noktalar.append((W + 20, 1150))
        k.cizgi(noktalar, fill=(140, 180, 255, 34), width=2)
    img.alpha_composite(k.bitir())
    resim, yer = _filigran(tema, rnd)
    if resim is not None:
        c.yapistir(img, resim, *yer)
    # kenar kararması (vinyet)
    maske = Image.new("L", (W // 8, H // 8), 0)
    ImageDraw.Draw(maske).ellipse((-W // 16, -H // 20, W // 8 + W // 16, H // 8 + H // 20), fill=255)
    maske = maske.filter(ImageFilter.GaussianBlur(18)).resize((W, H))
    karanlik = Image.new("RGBA", (W, H), (0, 0, 0, 150))
    karanlik.putalpha(Image.eval(maske, lambda v: int(150 * (1 - v / 255))))
    img.alpha_composite(karanlik)
    return img


# ---------------------------------------------------------------- uçuşan efektler

class Parcaciklar:
    def __init__(self, tema, sayi=None):
        self.tur = tema["parcacik"]
        self.vurgu = tema["vurgu"]
        rnd = random.Random(tema["tohum"])
        sayi = sayi or {"toz": 18, "isilti": 0, "far": 6, "yagmur": 50, "hud": 0, "yok": 0}.get(self.tur, 0)
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
                d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 245, 220, int(20 + 40 * parlak)))
            elif tur == "isilti":
                x, y = x0, y0 * 0.55
                parlak = max(0.0, math.sin(t * 2.2 * hiz + faz))
                r = (2 + 4 * hiz) * parlak
                if r > 0.5:
                    d.line([(x - r * 2.5, y), (x + r * 2.5, y)], fill=(255, 255, 255, int(200 * parlak)), width=3)
                    d.line([(x, y - r * 2.5), (x, y + r * 2.5)], fill=(255, 255, 255, int(200 * parlak)), width=3)
            elif tur == "far":  # uzaktan geçen far izleri
                y = 1500 + (y0 % 300)
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

KAMERA_HAREKETLERI = ["yakinlas", "uzaklas", "sola", "saga"]
GECISLER = ["kaydir", "yakinlas", "solma"]


def kamera(z, x, hareket, miktar=0.04):
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
    if stil == "solma":
        return Image.blend(onceki, yeni, e)
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
MINOR_DIZILER = [
    [(0, 3, 7), (8, 12, 15), (3, 7, 10), (10, 14, 17)],   # i VI III VII
    [(0, 3, 7), (10, 14, 17), (8, 12, 15), (7, 11, 14)],  # i VII VI V
    [(0, 3, 7), (5, 8, 12), (8, 12, 15), (7, 11, 14)],    # i iv VI V
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
    akorlar, desen = rnd.choice(MINOR_DIZILER if enstruman in ("nabiz", "pad") else AKOR_DIZILERI), rnd.choice(DESENLER)
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
        if enstruman == "nabiz":  # ciddi: alçak pad, sekizlik bas nabzı, hafif davul
            if i % 8 == 0:
                parca = sum(_nota("pad", midi_f(kok + a - 12), sekizlik * 8.5, sr) for a in akor) * 0.28
                iz[bas:bas + len(parca)] += parca
            basnota = _nota("bas", midi_f(kok - 24 + akor[0]), sekizlik * 0.9, sr) * (0.45 if i % 2 == 0 else 0.28)
            iz[bas:bas + len(basnota)] += basnota
            if i % 4 == 0:
                davul = _nota("davul", 0, 0.4, sr) * 0.5
                iz[bas:bas + len(davul)] += davul
        elif enstruman == "pad":
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
