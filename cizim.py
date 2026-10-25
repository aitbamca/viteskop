"""Sahne çizimleri. Hepsi kodla çiziliyor: ücretsiz, telifsiz ve her videoda aynı stil.

Arabalar marka/model taklidi değildir: sade, genel silüetlerdir (sedan, suv, hatchback).
"""
import math
import os

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
S = 2  # kenarlar yumuşak olsun diye 2 kat büyük çizip küçültüyoruz

_KOK = os.path.dirname(os.path.abspath(__file__))
_FONT_KLASORU = os.path.join(_KOK, "marka", "fontlar")
FONT_KALIN = os.path.join(_FONT_KLASORU, "InterDisplay-ExtraBold.otf")
FONT_NORMAL = os.path.join(_FONT_KLASORU, "InterDisplay-Medium.otf")
FONT_LOGO = os.path.join(_FONT_KLASORU, "InterDisplay-BlackItalic.otf")
_fontlar = {}

# Viteskop renkleri: koyu grafit zemin, kehribar (gösterge ışığı) vurgu, mavi ikincil
GRAFIT, KOYU, BEYAZ = (20, 23, 31), (12, 14, 20), (255, 255, 255)
KEHRIBAR, MAVI, KIRMIZI, YESIL = (255, 176, 0), (47, 128, 237), (229, 57, 53), (39, 174, 96)
GRI, ACIK_GRI = (120, 128, 145), (196, 202, 214)
TURUNCU_MARKA = (255, 110, 10)  # logodaki turuncu (sayfa sahibinin logosu: marka/logo.png)
# video.py ve eski sahneler bu adları kullanır
LACIVERT, MARKA_TURUNCU, SARI, TURUNCU = GRAFIT, TURUNCU_MARKA, (255, 214, 60), (245, 150, 40)
LOGO_DOSYASI = os.path.join(_KOK, "marka", "logo.png")

SERILER = {  # senaryoda "seri": "kafa" gibi yazılır
    "kafa": {"ad": "KAFA KAFAYA", "renk": KIRMIZI, "tema": "showroom", "soru": "Sen hangisini seçerdin?"},
    "bakim": {"ad": "BAKIM SAATİ", "renk": YESIL, "tema": "garaj", "soru": "Sen bunu ne sıklıkla yapıyorsun?"},
    "ariza": {"ad": "ARIZA ALARMI", "renk": KEHRIBAR, "tema": "gosterge", "soru": "Bu sende hiç oldu mu?"},
    "parca": {"ad": "PARÇA REHBERİ", "renk": MAVI, "tema": "garaj", "soru": "Sen hangisini kullanıyorsun?"},
}


def font(boyut, kalin=True, logo=False):
    anahtar = (boyut, kalin, logo)
    if anahtar not in _fontlar:
        _fontlar[anahtar] = ImageFont.truetype(FONT_LOGO if logo else FONT_KALIN if kalin else FONT_NORMAL, boyut)
    return _fontlar[anahtar]


class Kalem:
    """Koordinatlar son boyutta verilir, içeride S kat büyük çizilir."""

    def __init__(self, w, h):
        self.img = Image.new("RGBA", (int(w * S), int(h * S)), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)

    def _k(self, kutu):
        return [v * S for v in kutu]

    def elips(self, kutu, fill=None, outline=None, width=0):
        self.d.ellipse(self._k(kutu), fill=fill, outline=outline, width=int(width * S))

    def daire(self, cx, cy, r, **kw):
        self.elips((cx - r, cy - r, cx + r, cy + r), **kw)

    def cokgen(self, noktalar, fill=None, outline=None, width=0):
        self.d.polygon([(x * S, y * S) for x, y in noktalar], fill=fill, outline=outline, width=int(width * S))

    def cizgi(self, noktalar, fill, width):
        self.d.line([(x * S, y * S) for x, y in noktalar], fill=fill, width=int(width * S), joint="curve")

    def kutu(self, kutu, fill=None, r=0, outline=None, width=0):
        self.d.rounded_rectangle(self._k(kutu), radius=r * S, fill=fill, outline=outline, width=int(width * S))

    def yay(self, kutu, bas, son, fill, width):
        self.d.arc(self._k(kutu), bas, son, fill=fill, width=int(width * S))

    def dilim(self, kutu, bas, son, fill):
        self.d.pieslice(self._k(kutu), bas, son, fill=fill)

    def yazi(self, x, y, metin, boyut, renk, kalin=True, anchor="mm"):
        self.d.text((x * S, y * S), metin, font=font(int(boyut * S), kalin), fill=renk, anchor=anchor)

    def bitir(self):
        return self.img.resize((self.img.width // S, self.img.height // S), Image.LANCZOS)


def yapistir(zemin, resim, x, y):
    """alpha_composite, ama taşan kısımları kırparak."""
    x, y = int(x), int(y)
    sol, ust = max(0, -x), max(0, -y)
    sag, alt = min(resim.width, zemin.width - x), min(resim.height, zemin.height - y)
    if sag <= sol or alt <= ust:
        return
    zemin.alpha_composite(resim.crop((sol, ust, sag, alt)), dest=(x + sol, y + ust))


def ortala_yapistir(zemin, resim, cx, cy):
    yapistir(zemin, resim, cx - resim.width / 2, cy - resim.height / 2)


def olcekle(resim, k):
    return resim.resize((max(1, int(resim.width * k)), max(1, int(resim.height * k))), Image.LANCZOS)


def saydamlik(resim, a):
    """Resmin görünürlüğünü a (0-1) ile çarpar."""
    if a >= 1:
        return resim
    kopya = resim.copy()
    kopya.putalpha(kopya.getchannel("A").point(lambda v: int(v * max(0.0, a))))
    return kopya


def gradyan(ust, alt):
    sutun = Image.new("RGB", (1, H))
    for y in range(H):
        t = y / (H - 1)
        sutun.putpixel((0, y), tuple(int(a + (b - a) * t) for a, b in zip(ust, alt)))
    return sutun.resize((W, H)).convert("RGBA")


def metin_ciz(zemin, metin, cx, cy, boyut, renk, kontur=(255, 255, 255), kontur_kalinlik=0, kalin=True):
    d = ImageDraw.Draw(zemin)
    d.text((cx, cy), metin, font=font(boyut, kalin), fill=renk, anchor="mm",
           stroke_width=kontur_kalinlik, stroke_fill=kontur)


def renk_karistir(a, b, t):
    """İki renk arasında t (0-1) oranında geçiş."""
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


def koyu(renk, k):
    return tuple(max(0, min(255, int(v * k))) for v in renk[:3])


# ---------------------------------------------------------------- marka

def logo(genislik=900, acik_zemin=False):
    """Sayfa sahibinin logosu (marka/logo.png, siyah zemin kırpılır); yoksa kodla çizilen yedek logo."""
    if os.path.exists(LOGO_DOSYASI) and not acik_zemin:
        resim = Image.open(LOGO_DOSYASI).convert("RGBA")
        gri = resim.convert("L").point(lambda v: 255 if v > 40 else 0)  # siyah zemini at
        kutu = gri.getbbox() or (0, 0, resim.width, resim.height)
        resim = resim.crop(kutu)
        return olcekle(resim, genislik / resim.width)
    return _yedek_logo(genislik, acik_zemin)


def _yedek_logo(genislik=900, acik_zemin=False):
    """VITESKOP yazısı ve solunda hız göstergesi. Koyu zemin için beyaz, açık zemin için grafit yazı."""
    h = int(genislik * 0.28)
    genislik = max(genislik, int(h * 0.84 + 40 + font(int(h * 0.5), logo=True).getlength("VITESKOP") + 20))
    k = Kalem(genislik, h)
    r = h * 0.42
    cx, cy = r + 6, h * 0.56
    yazi_renk = GRAFIT if acik_zemin else BEYAZ
    k.yay((cx - r, cy - r, cx + r, cy + r), 150, 390, fill=yazi_renk, width=r * 0.17)
    k.yay((cx - r, cy - r, cx + r, cy + r), 300, 390, fill=TURUNCU_MARKA, width=r * 0.17)
    for i in range(7):  # kadran çizgileri
        a = math.radians(150 + i * 40)
        k.cizgi([(cx + math.cos(a) * r * 0.62, cy + math.sin(a) * r * 0.62),
                 (cx + math.cos(a) * r * 0.74, cy + math.sin(a) * r * 0.74)], fill=yazi_renk, width=r * 0.07)
    a = math.radians(325)
    k.cizgi([(cx, cy), (cx + math.cos(a) * r * 0.78, cy + math.sin(a) * r * 0.78)], fill=TURUNCU_MARKA, width=r * 0.11)
    k.daire(cx, cy, r * 0.13, fill=TURUNCU_MARKA)
    resim = k.bitir()
    ImageDraw.Draw(resim).text((2 * r + 28, h * 0.53), "VITESKOP", font=font(int(h * 0.5), logo=True), fill=yazi_renk, anchor="lm")
    return resim.crop(resim.getbbox())


def logo_karti(genislik, ic_bosluk=18, yaricap=26):
    """Videonun üstündeki küçük logo: siyah cam kart üzerinde."""
    l = logo(int((genislik - 2 * ic_bosluk) * 2))
    l = olcekle(l, (genislik - 2 * ic_bosluk) / l.width)
    kart = Image.new("RGBA", (genislik, l.height + 2 * ic_bosluk), (0, 0, 0, 0))
    ImageDraw.Draw(kart).rounded_rectangle((0, 0, kart.width - 1, kart.height - 1), radius=yaricap, fill=(0, 0, 0, 215))
    kart.alpha_composite(l, dest=(ic_bosluk, ic_bosluk))
    return kart


def seri_rozeti(seri, boyut=40):
    """Serinin adı, renkli hap içinde: KAFA KAFAYA, BAKIM SAATİ…"""
    bilgi = SERILER.get(seri)
    if not bilgi:
        return None
    f = font(boyut)
    w = int(f.getlength(bilgi["ad"]) + boyut * 2.2)
    h = int(boyut * 1.9)
    k = Kalem(w, h)
    k.kutu((0, 0, w, h), fill=bilgi["renk"], r=h / 2)
    k.daire(h * 0.5, h / 2, boyut * 0.22, fill=BEYAZ)
    resim = k.bitir()
    ImageDraw.Draw(resim).text((h * 0.5 + boyut * 0.55, h / 2), bilgi["ad"], font=f, fill=BEYAZ, anchor="lm")
    return resim


# ---------------------------------------------------------------- araba

GOVDELER = {
    # alt gövde üst çizgisi (y), kabin noktaları, teker yarıçapı
    "sedan": {"omuz": 172, "kabin": [(205, 172), (285, 98), (525, 94), (628, 172)], "r": 60, "alt": 268},
    "suv": {"omuz": 140, "kabin": [(160, 140), (218, 58), (580, 54), (650, 140)], "r": 70, "alt": 262},
    "hatchback": {"omuz": 172, "kabin": [(150, 172), (190, 92), (470, 90), (590, 172)], "r": 60, "alt": 268},
    "pickup": {"omuz": 160, "kabin": [(330, 160), (370, 78), (560, 74), (640, 160)], "r": 68, "alt": 278},
}


def araba(w=800, renk=(47, 128, 237), tip="sedan", teker_aci=0.0, yon=1, farlar=False):
    """Yandan sade araba silüeti. yon=1 sağa bakar. teker_aci: jantların dönüşü (derece)."""
    g = GOVDELER.get(tip, GOVDELER["sedan"])
    k = Kalem(800, 340)
    koyu_renk, acik_renk = koyu(renk, 0.72), renk_karistir(renk, (255, 255, 255), 0.35)
    alt, omuz, r = g["alt"], g["omuz"], g["r"]
    tx = (175, 625)
    k.elips((40, 300, 760, 330), fill=(0, 0, 0, 90))  # gölge
    # kabin ve camlar
    kabin = g["kabin"]
    k.cokgen(kabin + [(kabin[-1][0], omuz + 8), (kabin[0][0], omuz + 8)], fill=renk)
    ic = [(kabin[0][0] + 24, omuz), (kabin[1][0] + 14, kabin[1][1] + 12), (kabin[2][0] - 10, kabin[2][1] + 12), (kabin[3][0] - 34, omuz)]
    k.cokgen(ic, fill=(150, 196, 228))
    k.cokgen([(ic[1][0] + 30, ic[1][1]), (ic[1][0] + 70, ic[1][1]), (ic[0][0] + 60, omuz), (ic[0][0] + 20, omuz)], fill=(200, 226, 245, 160))
    orta = (ic[1][0] + ic[2][0]) / 2
    k.cokgen([(orta - 8, ic[1][1] - 2), (orta + 8, ic[1][1] - 2), (orta + 12, omuz), (orta - 12, omuz)], fill=renk)
    if tip == "pickup":  # kasa
        k.kutu((50, omuz - 4, 335, omuz + 20), fill=koyu_renk, r=6)
    # alt gövde
    govde = [(48, alt), (38, omuz + 40), (60, omuz + 4), (150, omuz - 4), (680, omuz - 2), (750, omuz + 22), (772, omuz + 60), (770, alt - 8), (756, alt)]
    k.cokgen(govde, fill=renk)
    k.cokgen([(60, omuz + 4), (150, omuz - 4), (680, omuz - 2), (750, omuz + 22), (740, omuz + 30), (150, omuz + 12)], fill=acik_renk)
    k.kutu((40, alt - 26, 772, alt + 2), fill=koyu_renk, r=10)
    # kapı çizgileri ve kollar
    for x in (orta - 6, orta + 175 if tip != "pickup" else orta + 140):
        if 120 < x < 700:
            k.cizgi([(x, omuz + 6), (x - 4, alt - 30)], fill=koyu_renk, width=3)
    k.kutu((orta - 70, omuz + 26, orta - 36, omuz + 34), fill=koyu_renk, r=3)
    k.kutu((orta + 110, omuz + 26, orta + 144, omuz + 34), fill=koyu_renk, r=3)
    # farlar
    k.cokgen([(744, omuz + 22), (770, omuz + 40), (768, omuz + 56), (738, omuz + 46)], fill=(255, 244, 200))
    k.kutu((40, omuz + 30, 60, omuz + 58), fill=KIRMIZI, r=5)
    if farlar:
        k.cokgen([(768, omuz + 40), (800, omuz + 20), (800, omuz + 90), (768, omuz + 56)], fill=(255, 244, 200, 90))
    # teker yuvaları ve tekerler
    for x in tx:
        k.dilim((x - r - 14, alt - r - 40 - 14, x + r + 14, alt - 40 + r + 14), 180, 360, fill=(26, 28, 34))
    for x in tx:
        cy = 310 - r
        k.daire(x, cy, r, fill=(30, 32, 38))
        k.daire(x, cy, r * 0.62, fill=(205, 210, 220))
        k.daire(x, cy, r * 0.5, fill=(150, 156, 170))
        for i in range(5):
            a = math.radians(teker_aci * yon + i * 72)
            k.cizgi([(x, cy), (x + math.cos(a) * r * 0.55, cy + math.sin(a) * r * 0.55)], fill=(220, 224, 232), width=r * 0.16)
        k.daire(x, cy, r * 0.14, fill=(90, 96, 110))
    resim = k.bitir()
    if yon < 0:
        resim = resim.transpose(Image.FLIP_LEFT_RIGHT)
    return olcekle(resim, w / 800) if w != 800 else resim


# ---------------------------------------------------------------- gösterge ve ikaz lambaları

def gosterge(r=260, deger=0.5, renk=KEHRIBAR, yazi=None, alt_yazi=None):
    """Hız/devir göstergesi: deger 0-1 iğnenin yeri."""
    boyut = int(r * 2 + 20)
    k = Kalem(boyut, boyut)
    c = boyut / 2
    k.daire(c, c, r, fill=(18, 21, 30, 240))
    k.daire(c, c, r, outline=(70, 78, 96), width=r * 0.03)
    bas, aralik = 135, 270
    k.yay((c - r * 0.86, c - r * 0.86, c + r * 0.86, c + r * 0.86), bas, bas + aralik, fill=(48, 54, 70), width=r * 0.07)
    if deger > 0:
        k.yay((c - r * 0.86, c - r * 0.86, c + r * 0.86, c + r * 0.86), bas, bas + aralik * min(1, deger), fill=renk, width=r * 0.07)
    for i in range(11):
        a = math.radians(bas + aralik * i / 10)
        uzun = i % 2 == 0
        k.cizgi([(c + math.cos(a) * r * (0.66 if uzun else 0.71), c + math.sin(a) * r * (0.66 if uzun else 0.71)),
                 (c + math.cos(a) * r * 0.77, c + math.sin(a) * r * 0.77)], fill=(220, 226, 236), width=r * (0.025 if uzun else 0.015))
    a = math.radians(bas + aralik * max(0, min(1, deger)))
    k.cizgi([(c - math.cos(a) * r * 0.1, c - math.sin(a) * r * 0.1), (c + math.cos(a) * r * 0.72, c + math.sin(a) * r * 0.72)], fill=KIRMIZI, width=r * 0.04)
    k.daire(c, c, r * 0.07, fill=(230, 232, 238))
    resim = k.bitir()
    d = ImageDraw.Draw(resim)
    if yazi:
        d.text((c, c + r * 0.3), yazi, font=font(int(r * 0.19)), fill=BEYAZ, anchor="mm")
    if alt_yazi:
        d.text((c, c + r * 0.5), alt_yazi, font=font(int(r * 0.1), kalin=False), fill=ACIK_GRI, anchor="mm")
    return resim


IKAZ_RENKLERI = {"kirmizi": KIRMIZI, "sari": KEHRIBAR, "yesil": YESIL, "mavi": MAVI}


def ikaz_lambasi(ikon="motor", boyut=300, renk=KEHRIBAR, parlak=1.0):
    """Gösterge panelindeki ikaz simgeleri: motor, yag, aku, sicaklik, fren, lastik, abs, hava_yastigi."""
    k = Kalem(boyut, boyut)
    s = boyut / 100  # simgeler 100x100 düzlemde tanımlı
    renk = renk + (int(255 * (0.35 + 0.65 * parlak)),)
    if parlak > 0.5:  # hafif ışık halesi
        k.daire(50 * s, 50 * s, 49 * s, fill=renk[:3] + (int(22 * parlak),))

    def p(*noktalar):
        return [(x * s, y * s) for x, y in noktalar]

    w = 6 * s
    if ikon == "motor":
        k.cokgen(p((22, 38), (34, 38), (34, 32), (56, 32), (60, 38), (70, 38), (70, 46), (78, 46), (78, 40), (84, 40),
                   (84, 64), (78, 64), (78, 58), (70, 58), (64, 70), (34, 70), (28, 62), (22, 62)), fill=renk)
        k.cokgen(p((40, 26), (54, 26), (54, 32), (40, 32)), fill=renk)
        k.cokgen(p((12, 44), (22, 44), (22, 58), (12, 58)), fill=renk)
    elif ikon == "yag":
        k.cokgen(p((18, 52), (30, 44), (58, 44), (82, 36), (86, 40), (64, 64), (18, 64)), fill=renk)
        k.cokgen(p((30, 44), (34, 36), (44, 36), (46, 44)), fill=renk)
        k.cizgi(p((12, 46), (20, 52)), fill=renk, width=w)
        k.elips((84 * s, 50 * s, 92 * s, 62 * s), fill=renk)
    elif ikon == "aku":
        k.kutu((14 * s, 32 * s, 86 * s, 72 * s), outline=renk, width=w, r=4 * s)
        k.kutu((24 * s, 24 * s, 36 * s, 32 * s), fill=renk)
        k.kutu((64 * s, 24 * s, 76 * s, 32 * s), fill=renk)
        k.cizgi(p((24, 52), (36, 52)), fill=renk, width=w * 0.8)
        k.cizgi(p((30, 46), (30, 58)), fill=renk, width=w * 0.8)
        k.cizgi(p((64, 52), (76, 52)), fill=renk, width=w * 0.8)
    elif ikon == "sicaklik":
        k.cizgi(p((50, 14), (50, 56)), fill=renk, width=w * 1.3)
        k.daire(50 * s, 62 * s, 9 * s, fill=renk)
        for y in (24, 34, 44):
            k.cizgi(p((50, y), (62, y)), fill=renk, width=w * 0.7)
        for y in (76, 86):
            k.cizgi(p((14, y), (24, y - 4), (34, y), (44, y - 4), (56, y), (66, y - 4), (76, y), (86, y - 4)), fill=renk, width=w * 0.7)
    elif ikon in ("fren", "abs"):
        k.daire(50 * s, 50 * s, 26 * s, outline=renk, width=w)
        k.yay((10 * s, 14 * s, 50 * s, 86 * s), 120, 240, fill=renk, width=w)
        k.yay((50 * s, 14 * s, 90 * s, 86 * s), 300, 420, fill=renk, width=w)
        if ikon == "fren":
            k.cizgi(p((50, 36), (50, 54)), fill=renk, width=w)
            k.daire(50 * s, 62 * s, 3.6 * s, fill=renk)
        else:
            k.yazi(50 * s, 51 * s, "ABS", 15 * s, renk)
    elif ikon in ("lastik", "lastik_basinci"):
        k.cokgen(p((22, 30), (32, 30), (32, 56), (36, 64), (64, 64), (68, 56), (68, 30), (78, 30), (78, 58), (70, 74), (30, 74), (22, 58)), fill=renk)
        for x in (26, 38, 50, 62, 74):
            k.cizgi(p((x, 78), (x, 84)), fill=renk, width=w * 0.8)
        k.cizgi(p((50, 34), (50, 52)), fill=renk, width=w)
        k.daire(50 * s, 59 * s, 3.4 * s, fill=renk)
    elif ikon == "hava_yastigi":
        k.daire(36 * s, 22 * s, 8 * s, fill=renk)
        k.cizgi(p((36, 34), (40, 58), (58, 58), (64, 80)), fill=renk, width=w * 1.4)
        k.daire(70 * s, 40 * s, 16 * s, fill=renk)
    return k.bitir()


# ---------------------------------------------------------------- parçalar

def parca(ad="lastik", boyut=420, aci=0.0, yazili=True):
    """Parça çizimleri: lastik, fren_diski, aku, yag_bidonu, buji, anahtar, filtre, silecek."""
    k = Kalem(boyut, boyut)
    s = boyut / 100
    c = boyut / 2

    def p(*noktalar):
        return [(x * s, y * s) for x, y in noktalar]

    if ad == "lastik":
        k.daire(c, c, 46 * s, fill=(34, 36, 42))
        for i in range(24):  # diş desen
            a = math.radians(aci + i * 15)
            k.cizgi([(c + math.cos(a) * 40 * s, c + math.sin(a) * 40 * s), (c + math.cos(a) * 46 * s, c + math.sin(a) * 46 * s)], fill=(60, 64, 74), width=3 * s)
        k.daire(c, c, 28 * s, fill=(200, 206, 216))
        k.daire(c, c, 23 * s, fill=(140, 146, 160))
        for i in range(5):
            a = math.radians(aci + i * 72)
            k.cizgi([(c, c), (c + math.cos(a) * 25 * s, c + math.sin(a) * 25 * s)], fill=(226, 230, 238), width=6 * s)
        k.daire(c, c, 6 * s, fill=(90, 96, 110))
    elif ad == "fren_diski":
        k.daire(c, c, 44 * s, fill=(170, 174, 182))
        k.daire(c, c, 44 * s, outline=(120, 124, 134), width=2 * s)
        for i in range(12):
            a = math.radians(aci + i * 30)
            k.daire(c + math.cos(a) * 34 * s, c + math.sin(a) * 34 * s, 2.4 * s, fill=(110, 114, 124))
        k.daire(c, c, 22 * s, fill=(130, 134, 144))
        for i in range(5):
            a = math.radians(aci + i * 72)
            k.daire(c + math.cos(a) * 13 * s, c + math.sin(a) * 13 * s, 3 * s, fill=(70, 74, 84))
        k.daire(c, c, 6 * s, fill=(70, 74, 84))
        k.kutu((70 * s, 22 * s, 92 * s, 60 * s), fill=KIRMIZI, r=6 * s)  # kaliper
        if yazili:
            k.yazi(81 * s, 41 * s, "V", 10 * s, BEYAZ)
    elif ad == "aku":
        k.cokgen(p((14, 34), (70, 34), (86, 24), (30, 24)), fill=(70, 76, 90))
        k.cokgen(p((70, 34), (86, 24), (86, 70), (70, 82)), fill=(30, 34, 44))
        k.kutu((14 * s, 34 * s, 70 * s, 82 * s), fill=(44, 50, 64))
        k.kutu((26 * s, 16 * s, 34 * s, 28 * s), fill=KIRMIZI, r=2 * s)
        k.kutu((58 * s, 16 * s, 66 * s, 28 * s), fill=(40, 40, 46), r=2 * s)
        k.kutu((20 * s, 48 * s, 64 * s, 64 * s), fill=KEHRIBAR, r=3 * s)
        if yazili:
            k.yazi(42 * s, 56.5 * s, "12V", 10 * s, GRAFIT)
    elif ad == "yag_bidonu":
        k.kutu((24 * s, 26 * s, 76 * s, 88 * s), fill=KEHRIBAR, r=8 * s)
        k.kutu((54 * s, 14 * s, 68 * s, 28 * s), fill=GRAFIT, r=3 * s)
        k.kutu((30 * s, 18 * s, 50 * s, 26 * s), outline=koyu(KEHRIBAR, 0.75), width=4 * s, r=4 * s)
        k.kutu((30 * s, 44 * s, 70 * s, 74 * s), fill=GRAFIT, r=4 * s)
        if yazili:
            k.yazi(50 * s, 54 * s, "5W-30", 9 * s, BEYAZ)
            k.elips((44 * s, 60 * s, 56 * s, 72 * s), fill=KEHRIBAR)
    elif ad == "buji":
        k.kutu((44 * s, 8 * s, 56 * s, 20 * s), fill=(170, 176, 186), r=2 * s)
        k.kutu((40 * s, 18 * s, 60 * s, 48 * s), fill=(244, 244, 240), r=6 * s)
        k.cokgen(p((36, 48), (64, 48), (66, 60), (34, 60)), fill=(150, 156, 168))
        for y in range(62, 84, 4):
            k.cizgi(p((40, y), (60, y + 2)), fill=(170, 176, 186), width=2.4 * s)
        k.kutu((40 * s, 60 * s, 60 * s, 84 * s), outline=(120, 126, 138), width=1.5 * s)
        k.cizgi(p((50, 84), (50, 92), (56, 92)), fill=(120, 126, 138), width=2.4 * s)
    elif ad == "anahtar":
        k.cizgi(p((26, 74), (66, 34)), fill=(196, 202, 214), width=11 * s)
        k.daire(72 * s, 28 * s, 14 * s, fill=(196, 202, 214))
        k.cokgen(p((70, 18), (82, 10), (88, 24), (78, 32)), fill=(0, 0, 0, 0))
        k.daire(78 * s, 22 * s, 6 * s, fill=(0, 0, 0, 0))
        k.daire(22 * s, 78 * s, 10 * s, fill=(196, 202, 214))
        k.daire(22 * s, 78 * s, 5 * s, fill=(110, 116, 130))
    elif ad == "filtre":
        k.elips((26 * s, 16 * s, 74 * s, 28 * s), fill=(220, 224, 230))
        k.kutu((26 * s, 22 * s, 74 * s, 82 * s), fill=MAVI)
        for x in range(30, 72, 6):
            k.cizgi(p((x, 26), (x, 80)), fill=koyu(MAVI, 0.75), width=1.8 * s)
        k.elips((26 * s, 76 * s, 74 * s, 88 * s), fill=koyu(MAVI, 0.6))
        k.elips((40 * s, 18 * s, 60 * s, 26 * s), fill=(150, 156, 168))
    elif ad == "silecek":
        k.cizgi(p((14, 70), (86, 40)), fill=(40, 42, 50), width=6 * s)
        k.cizgi(p((16, 74), (88, 44)), fill=(20, 22, 26), width=3 * s)
        k.cizgi(p((50, 56), (60, 90)), fill=(60, 64, 74), width=5 * s)
    resim = k.bitir()
    return resim


# ---------------------------------------------------------------- animasyon ve yazı yardımcıları

def sadelestir(kelime):
    return kelime.lower().strip(".,!?:;'\"")


def zaman_bul(kz, bas, varsayilan=0.0, sira=0):
    """Sahne metninde `bas` ile başlayan kelimenin (sira'ncı geçişinin) okunduğu an."""
    eslesen = [b for k, b, _ in kz if sadelestir(k).startswith(bas)]
    return eslesen[sira] if len(eslesen) > sira else varsayilan


def pop(t, t0, sure=0.35):
    """t0'da sıfırdan büyüyüp hafif taşarak 1'e oturan ölçek."""
    if t < t0:
        return 0.0
    x = (t - t0) / sure
    return 1.0 if x >= 1 else x + 0.3 * math.sin(x * math.pi)


def kayarak(t, t0, sure=0.4):
    """t0'dan sonra 0→1 yumuşak ilerleme (kayarak girişler için)."""
    if t < t0:
        return 0.0
    x = min(1.0, (t - t0) / sure)
    return 1 - (1 - x) ** 3


def flas(zemin, guc):
    if guc > 0.01:
        zemin.alpha_composite(Image.new("RGBA", zemin.size, (255, 255, 240, int(220 * guc))))


def etiket(zemin, metin, cx, cy, boyut=46, zemin_rengi=KOYU + (225,), renk=BEYAZ, olcek=1.0, cerceve=None):
    """Yuvarlak köşeli kart içinde yazı; olcek 0 ise çizilmez (pop ile birlikte kullanılır)."""
    if olcek <= 0:
        return
    boyut = max(8, int(boyut * olcek))
    f = font(boyut)
    sol, ust, sag, alt = f.getbbox(metin)
    w, h = sag - sol + boyut * 1.1, alt - ust + boyut * 0.8
    katman = Image.new("RGBA", (int(w), int(h)), (0, 0, 0, 0))
    ImageDraw.Draw(katman).rounded_rectangle((0, 0, w - 1, h - 1), radius=int(h / 2), fill=zemin_rengi,
                                             outline=cerceve, width=3 if cerceve else 0)
    metin_ciz(katman, metin, w / 2, h / 2, boyut, renk)
    ortala_yapistir(zemin, katman, cx, cy)


def kart(w, h, renk=KOYU + (215,), cerceve=None, r=36):
    """Koyu cam kart (yazıların arkası)."""
    k = Kalem(w, h)
    k.kutu((0, 0, w, h), fill=renk, r=r, outline=cerceve, width=3 if cerceve else 0)
    return k.bitir()


def konusma_balonu(metin, boyut=110, renk=KEHRIBAR):
    w, h = 300, 260
    k = Kalem(w, h)
    k.elips((0, 0, w, 210), fill=KOYU + (235,), outline=renk, width=6)
    k.cokgen([(70, 178), (130, 196), (40, 255)], fill=renk)
    resim = k.bitir()
    metin_ciz(resim, metin, w / 2, 105, boyut, renk)
    return resim


def satirlara_sar(metin, boyut, genislik, kalin=True):
    f, satirlar, satir = font(boyut, kalin), [], ""
    for kelime in metin.split():
        aday = (satir + " " + kelime).strip()
        if satir and f.getlength(aday) > genislik:
            satirlar.append(satir)
            satir = kelime
        else:
            satir = aday
    return satirlar + [satir] if satir else satirlar


# ---------------------------------------------------------------- çizgisel (teknik) çizimler

def cizgisel(resim, renk=(232, 236, 243), kalinlik=3, vurgu=None, vurgu_esik=None):
    """Dolu bir çizimi teknik çizim gibi kontur çizgilerine çevirir (kenar algılama)."""
    from PIL import ImageChops, ImageFilter
    a = resim.getchannel("A")
    l = resim.convert("L")
    dis = a.filter(ImageFilter.FIND_EDGES).point(lambda v: 255 if v > 60 else 0)
    ic = l.filter(ImageFilter.FIND_EDGES).point(lambda v: 255 if v > 40 else 0)
    ic = ImageChops.multiply(ic, a.point(lambda v: 255 if v > 200 else 0))
    kenar = ImageChops.lighter(dis, ic)
    if kalinlik > 1:
        kenar = kenar.filter(ImageFilter.MaxFilter(kalinlik if kalinlik % 2 else kalinlik + 1))
    cizgi = Image.new("RGBA", resim.size, renk + (0,))
    cizgi.putalpha(kenar)
    return cizgi


def _egri(noktalar, adim=8):
    """Catmull-Rom: köşeli nokta dizisini yumuşak eğriye çevirir."""
    sonuc = []
    p = [noktalar[0]] + list(noktalar) + [noktalar[-1]]
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        for j in range(adim):
            t = j / adim
            t2, t3 = t * t, t * t * t
            sonuc.append(tuple(0.5 * ((2 * p1[k]) + (-p0[k] + p2[k]) * t + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2
                                      + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3) for k in range(2)))
    sonuc.append(noktalar[-1])
    return sonuc


PROFILLER = {
    # üst kontur (arkadan öne), cam çizgisi, teker merkezleri/yarıçap, alt çizgi y
    "sedan": {"ust": [(38, 262), (34, 222), (58, 186), (150, 172), (215, 164), (305, 104), (420, 90), (520, 98), (612, 160),
                      (705, 176), (768, 198), (782, 238), (772, 264)],
              "cam": [(222, 163), (308, 112), (418, 100), (512, 106), (590, 160)], "orta": 420, "teker": (178, 628), "r": 62, "alt": 264},
    "suv": {"ust": [(36, 256), (30, 196), (42, 130), (76, 82), (150, 68), (480, 64), (556, 78), (628, 138), (716, 156),
                    (772, 180), (786, 230), (776, 256)],
            "cam": [(66, 132), (94, 92), (152, 80), (470, 76), (546, 88), (604, 140)], "orta": 340, "teker": (178, 628), "r": 70, "alt": 252},
    "hatchback": {"ust": [(44, 262), (40, 214), (52, 158), (88, 110), (150, 94), (300, 88), (450, 94), (568, 156),
                          (690, 172), (762, 196), (778, 238), (768, 264)],
                  "cam": [(76, 158), (104, 116), (152, 102), (300, 98), (444, 104), (548, 156)], "orta": 300, "teker": (175, 615), "r": 62, "alt": 264},
    "pickup": {"ust": [(36, 256), (32, 180), (300, 178), (338, 176), (352, 140), (366, 98), (520, 90), (602, 148), (712, 162),
                       (772, 186), (784, 234), (774, 258)],
               "cam": [(374, 148), (388, 106), (514, 100), (582, 148)], "orta": 470, "teker": (190, 628), "r": 70, "alt": 252},
}


def araba_cizgi(w=800, tip="sedan", yon=1, teker_aci=0.0, renk=(232, 236, 243), vurgu=None):
    """Modern bir arabanın yandan teknik çizimi (yalnızca çizgiler). vurgu: jant ve far rengi."""
    pr = PROFILLER.get(tip, PROFILLER["sedan"])
    vurgu = vurgu or renk
    k = Kalem(800, 340)
    kal = 3.2
    r, alt = pr["r"], pr["alt"]
    tx = pr["teker"]
    cy = 312 - r
    # gövde üst konturu
    k.cizgi(_egri(pr["ust"]), fill=renk, width=kal)
    # alt çizgi: teker kemerleriyle
    bas, son = pr["ust"][0], pr["ust"][-1]
    k.cizgi([(son[0], son[1]), (tx[1] + r + 14, alt)], fill=renk, width=kal)
    k.yay((tx[1] - r - 14, cy - r - 14, tx[1] + r + 14, cy + r + 14), 180, 360, fill=renk, width=kal)
    k.cizgi([(tx[1] - r - 14, alt), (tx[0] + r + 14, alt)], fill=renk, width=kal)
    k.yay((tx[0] - r - 14, cy - r - 14, tx[0] + r + 14, cy + r + 14), 180, 360, fill=renk, width=kal)
    k.cizgi([(tx[0] - r - 14, alt), (bas[0], bas[1])], fill=renk, width=kal)
    # camlar ve direk
    cam = _egri(pr["cam"])
    k.cizgi(cam + [pr["cam"][0]], fill=renk + (200,), width=kal * 0.7)
    orta = pr["orta"]
    k.cizgi([(orta, min(y for x, y in pr["cam"]) + 4), (orta + 4, pr["cam"][0][1] + 2)], fill=renk + (200,), width=kal * 0.7)
    # kapı çizgisi, karakter çizgisi, kollar
    k.cizgi([(orta + 2, pr["cam"][0][1] + 4), (orta - 2, alt - 6)], fill=renk + (150,), width=kal * 0.6)
    k.cizgi([(bas[0] + 20, 206), (son[0] - 30, 214)], fill=renk + (110,), width=kal * 0.5)
    for x in (orta - 70, orta + 120):
        if 100 < x < 700:
            k.cizgi([(x, 194), (x + 30, 194)], fill=renk + (170,), width=kal * 0.8)
    # farlar
    k.cizgi([(son[0] - 60, 192), (son[0] - 8, 206)], fill=vurgu, width=kal * 1.6)
    k.cizgi([(bas[0] + 2, 196), (bas[0] + 34, 190)], fill=(229, 57, 53), width=kal * 1.6)
    # tekerler
    for x in tx:
        k.daire(x, cy, r, outline=renk, width=kal)
        k.daire(x, cy, r * 0.66, outline=vurgu, width=kal * 0.8)
        for i in range(5):
            a = math.radians(teker_aci + i * 72)
            k.cizgi([(x + math.cos(a) * r * 0.16, cy + math.sin(a) * r * 0.16), (x + math.cos(a) * r * 0.6, cy + math.sin(a) * r * 0.6)],
                    fill=renk + (190,), width=kal * 0.7)
        k.daire(x, cy, r * 0.12, outline=renk, width=kal * 0.7)
    k.cizgi([(20, 314), (780, 314)], fill=renk + (70,), width=2)  # zemin
    resim = k.bitir()
    if yon < 0:
        resim = resim.transpose(Image.FLIP_LEFT_RIGHT)
    return olcekle(resim, w / 800) if w != 800 else resim


def parca_cizgi(ad, boyut=420, aci=0.0, renk=(232, 236, 243)):
    return olcekle(cizgisel(parca(ad, boyut * 2, aci=aci, yazili=False), renk, kalinlik=5), 0.5)
