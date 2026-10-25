"""Reels kapağı: dikkat çekici, büyük yazılı kapak görseli üretir (1080x1920 JPG).

Kullanım: python kapak.py senaryolar/X.json cikti/X.jpg

Instagram profil ızgarasında kapağın ortadaki 3:4'lük kısmı (y≈240–1680) görünür; her şey o alanda kalır.
Sayfa sahibinin görseli varsa (Viteskop Paneli → Haftalık Plan → Görsel yükle; oda müdürü kapaklar/'a koyar):
  kapaklar/YYYYAAGG-N.jpg       hazır, yazılı kapak: olduğu gibi kullanılır
  kapaklar/YYYYAAGG-N-arka.jpg  yalnızca arka plan: üstüne büyük yazılar ve logo eklenir
Senaryoda isteğe bağlı "kapak": {"satirlar": ["MOTOR YAĞI", "NE ZAMAN", "DEĞİŞİR?"], "vurgu": [2]}
(vurgu: turuncu yazılacak satırların sırası). Yoksa başlıktan üretilir.
"""
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import cizim as c

W, H = c.W, c.H
YAZI_UST, YAZI_ALT, GORSEL_UST = 290, 990, 960  # yazı bloğu ve görsel alanı (3:4 ızgara kesiminin içinde)
FONT_KAPAK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "marka", "fontlar", "Anton-Regular.ttf")


def buyuk(metin):
    """Türkçe büyük harf (i→İ, ı→I)."""
    return metin.replace("i", "İ").replace("ı", "I").upper()


def _font(boyut):
    return ImageFont.truetype(FONT_KAPAK, boyut)


def _parilti(resim, renk, yaricap=40, guc=1.0):
    """Resmin şeklinde renkli, bulanık ışık halesi."""
    a = resim.getchannel("A").filter(ImageFilter.GaussianBlur(yaricap))
    hale = Image.new("RGBA", resim.size, renk + (0,))
    hale.putalpha(a.point(lambda v: min(255, int(v * 1.6 * guc))))
    return hale


def _bosluklu(resim, pay):
    yeni = Image.new("RGBA", (resim.width + 2 * pay, resim.height + 2 * pay), (0, 0, 0, 0))
    yeni.alpha_composite(resim, (pay, pay))
    return yeni


def _yazi_satiri(metin, boyut, ust_renk, alt_renk, kontur_renk, kontur=14):
    """Kalın konturlu, dikey renk geçişli büyük yazı (YouTube kapağı tarzı)."""
    f = _font(boyut)
    sol, ust, sag, alt = f.getbbox(metin, stroke_width=kontur)
    w, h = sag - sol + 20, alt - ust + 20
    maske = Image.new("L", (w, h), 0)
    ImageDraw.Draw(maske).text((10 - sol, 10 - ust), metin, font=f, fill=255)
    kontur_maske = Image.new("L", (w, h), 0)
    ImageDraw.Draw(kontur_maske).text((10 - sol, 10 - ust), metin, font=f, fill=255, stroke_width=kontur, stroke_fill=255)
    gradyan = Image.new("RGBA", (1, h))
    for y in range(h):
        gradyan.putpixel((0, y), c.renk_karistir(ust_renk, alt_renk, y / max(1, h - 1)) + (255,))
    gradyan = gradyan.resize((w, h))
    satir = Image.new("RGBA", (w, h), kontur_renk + (0,))
    satir.putalpha(kontur_maske)
    dolgu = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dolgu.paste(gradyan, (0, 0), maske)
    satir.alpha_composite(dolgu)
    # üst kenarda ince parlama çizgisi
    parlama = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    p_maske = maske.filter(ImageFilter.GaussianBlur(2)).point(lambda v: 70 if v > 128 else 0)
    p_maske = Image.composite(p_maske, Image.new("L", (w, h), 0), Image.linear_gradient("L").rotate(180).resize((w, h)).point(lambda v: 255 if v > 190 else 0))
    parlama.putalpha(p_maske)
    satir.alpha_composite(parlama)
    return satir


def _ok(boyut, renk, aci=0):
    """Kıvrık kalın ok (dikkat çekmek için)."""
    k = c.Kalem(boyut, boyut)
    s = boyut / 100
    noktalar = [(14 * s + math.sin(t / 20 * math.pi) * 6 * s, (10 + t * 3.4) * s) for t in range(21)]
    noktalar = [(x + (y / s - 10) ** 1.6 * 0.035 * s, y) for x, y in noktalar]
    k.cizgi(noktalar, fill=renk, width=9 * s)
    uc = noktalar[-1]
    k.cokgen([(uc[0] - 13 * s, uc[1] - 8 * s), (uc[0] + 13 * s, uc[1] - 4 * s), (uc[0] + 1 * s, uc[1] + 13 * s)], fill=renk)
    resim = k.bitir()
    return resim.rotate(aci, resample=Image.BICUBIC, expand=True) if aci else resim


def _zemin(vurgu, merkez_y):
    z = c.gradyan((6, 7, 10), (16, 18, 24))
    k = c.Kalem(W, H)
    for x in range(0, W + 1, 60):
        k.cizgi([(x, 0), (x, H)], fill=(255, 255, 255, 8), width=1)
    for y in range(0, H + 1, 60):
        k.cizgi([(0, y), (W, y)], fill=(255, 255, 255, 8), width=1)
    z.alpha_composite(k.bitir())
    # vurgu renginde büyük ışık
    isik = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(isik).ellipse((W / 2 - 520, merkez_y - 420, W / 2 + 520, merkez_y + 420), fill=vurgu + (120,))
    z.alpha_composite(isik.filter(ImageFilter.GaussianBlur(160)))
    # ışık hüzmeleri
    hz = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(hz)
    for i in range(9):
        a = math.radians(-90 + (i - 4) * 18)
        d.polygon([(W / 2, merkez_y), (W / 2 + math.cos(a - 0.05) * 1600, merkez_y + math.sin(a - 0.05) * 1600),
                   (W / 2 + math.cos(a + 0.05) * 1600, merkez_y + math.sin(a + 0.05) * 1600)], fill=vurgu + (16,))
    z.alpha_composite(hz.filter(ImageFilter.GaussianBlur(8)))
    return z


def _gorsel(senaryo, vurgu):
    """Seriye göre büyük görsel ve merkezinin yüksekliği."""
    seri = senaryo.get("seri")
    sahneler = senaryo.get("sahneler", [])
    if seri == "kafa":
        kiyas = next((s for s in sahneler if s.get("tip") == "kiyas"), {})
        sol, sag = kiyas.get("sol", {}), kiyas.get("sag", {})
        a1 = c.araba_cizgi(620, sol.get("tip", "sedan"), yon=1, vurgu=vurgu, renk=(255, 255, 255))
        a2 = c.araba_cizgi(620, sag.get("tip", "sedan"), yon=-1, vurgu=(120, 170, 255), renk=(255, 255, 255))
        g = Image.new("RGBA", (W, 700), (0, 0, 0, 0))
        for resim, x, y, renk in ((a1, -60, 250, vurgu), (a2, 520, 250, (90, 150, 255))):
            kalin = resim.filter(ImageFilter.MaxFilter(5))
            g.alpha_composite(_parilti(kalin, renk, 26, 1.2), (x, y))
            g.alpha_composite(kalin, (x, y))
        vs = _yazi_satiri("VS", 230, (255, 255, 255), (255, 214, 120), (180, 20, 20), 16)
        g.alpha_composite(_parilti(vs, vurgu, 30), (W // 2 - vs.width // 2, 10))
        g.alpha_composite(vs, (W // 2 - vs.width // 2, 10))
        isimler = Image.new("RGBA", (W, 120), (0, 0, 0, 0))
        for metin, x, anchor in ((sol.get("ad", ""), 60, "lm"), (sag.get("ad", ""), W - 60, "rm")):
            ImageDraw.Draw(isimler).text((x, 60), buyuk(metin), font=_font(64), fill=(255, 255, 255), anchor=anchor,
                                         stroke_width=6, stroke_fill=(0, 0, 0))
        g.alpha_composite(isimler, (0, 500))
        return g, GORSEL_UST + 330
    if seri == "ariza":
        ikaz = next((s for s in sahneler if s.get("tip") == "ikaz"), {})
        renk = c.IKAZ_RENKLERI.get(ikaz.get("renk", "sari"), c.KEHRIBAR)
        lamba = _bosluklu(c.ikaz_lambasi(ikaz.get("ikon", "motor"), 520, renk, parlak=0.4), 140)
        g = Image.new("RGBA", (W, 700), (0, 0, 0, 0))
        x = W // 2 - lamba.width // 2
        g.alpha_composite(_parilti(lamba, renk, 70, 2.0), (x, 60 - 140))
        g.alpha_composite(_parilti(lamba, (255, 240, 200), 18, 0.8), (x, 60 - 140))
        g.alpha_composite(lamba, (x, 60 - 140))
        return g, GORSEL_UST + 330
    parca_sahnesi = next((s for s in sahneler if s.get("tip") == "parca"), None)
    if parca_sahnesi:
        resim = c.parca_cizgi(parca_sahnesi.get("parca", "lastik"), 540, renk=(255, 255, 255))
    else:
        tanim = senaryo.get("araba") or {}
        resim = c.araba_cizgi(980, tanim.get("tip", "sedan"), vurgu=vurgu, renk=(255, 255, 255))
    resim = resim.filter(ImageFilter.MaxFilter(3))
    g = Image.new("RGBA", (W, 700), (0, 0, 0, 0))
    x, y = W // 2 - resim.width // 2, 320 - resim.height // 2
    g.alpha_composite(_parilti(resim, vurgu, 40, 1.6), (x, y))
    g.alpha_composite(resim, (x, y))
    return g, GORSEL_UST + 330


def _ortali_yazi(z, satir, y, renkler, kontur_renk, en_boyut=230, genislik=980):
    """Ortalanmış büyük yazı satırı (gölgeli); kullandığı yüksekliği döndürür."""
    boyut = en_boyut
    while boyut > 80 and _font(boyut).getlength(satir) > genislik:
        boyut -= 6
    resim = _bosluklu(_yazi_satiri(satir, boyut, renkler[0], renkler[1], kontur_renk, 16), 40)
    golge = Image.new("RGBA", resim.size, (0, 0, 0, 0))
    golge.putalpha(resim.getchannel("A").filter(ImageFilter.GaussianBlur(14)).point(lambda v: int(v * 0.85)))
    z.alpha_composite(golge, (W // 2 - resim.width // 2 + 8, int(y) + 12 - 40))
    z.alpha_composite(resim, (W // 2 - resim.width // 2, int(y) - 40))
    return boyut


def kapak_kafa(senaryo):
    """Kafa Kafaya kapağı: üstte birinci model, ortada VS, altta ikinci model (sayfa sahibinin isteği)."""
    kiyas = next((s for s in senaryo.get("sahneler", []) if s.get("tip") == "kiyas"), {})
    sol, sag = kiyas.get("sol", {}), kiyas.get("sag", {})
    kirmizi, mavi = c.KIRMIZI, (70, 140, 255)
    z = _zemin(kirmizi, 520)
    alt_isik = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(alt_isik).ellipse((W / 2 - 520, 1230 - 380, W / 2 + 520, 1230 + 380), fill=mavi + (110,))
    z.alpha_composite(alt_isik.filter(ImageFilter.GaussianBlur(160)))
    for tanim, y, yon, renk in ((sol, 500, 1, kirmizi), (sag, 1010, -1, mavi)):
        ar = c.araba_cizgi(760, tanim.get("tip", "sedan"), yon=yon, vurgu=renk, renk=(255, 255, 255)).filter(ImageFilter.MaxFilter(5))
        ar = _bosluklu(ar, 60)
        x = W // 2 - ar.width // 2
        z.alpha_composite(_parilti(ar, renk, 26, 1.3), (x, y - 60))
        z.alpha_composite(ar, (x, y - 60))
    _ortali_yazi(z, sol.get("ad", "").upper(), 300, ((255, 255, 255), (196, 202, 214)), (150, 18, 18), 210)
    _ortali_yazi(z, "VS", 790, ((255, 214, 90), (255, 110, 10)), (90, 10, 0), 220)
    _ortali_yazi(z, sag.get("ad", "").upper(), 1360, ((255, 255, 255), (196, 202, 214)), (20, 40, 130), 210)
    rozet = c.seri_rozeti("kafa", 34)
    z.alpha_composite(rozet, (W // 2 - rozet.width // 2, 200))
    logo = c.logo(300)
    z.alpha_composite(logo, (W // 2 - logo.width // 2, 1690 - logo.height // 2))
    return _vinyet(z)


def _vinyet(z):
    maske = Image.new("L", (W // 8, H // 8), 0)
    ImageDraw.Draw(maske).ellipse((-W // 12, -H // 16, W // 8 + W // 12, H // 8 + H // 16), fill=255)
    maske = maske.filter(ImageFilter.GaussianBlur(14)).resize((W, H))
    karanlik = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    karanlik.putalpha(maske.point(lambda v: int(170 * (1 - v / 255))))
    z.alpha_composite(karanlik)
    return z.convert("RGB")


KAPAK_KLASORU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kapaklar")


def _hazir_gorsel(senaryo_yolu, ek=""):
    """kapaklar/ içinde sayfa sahibinin görseli: plan kimliğiyle (YYYYAAGG-N) ya da senaryo adıyla."""
    ad = os.path.splitext(os.path.basename(senaryo_yolu))[0]
    plan_id = "-".join(ad.split("-")[:2])
    for kok in (plan_id, ad):
        for uzanti in (".jpg", ".jpeg", ".png", ".webp"):
            yol = os.path.join(KAPAK_KLASORU, kok + ek + uzanti)
            if os.path.exists(yol):
                return yol
    return None


def _doldur(yol):
    """Görseli 1080x1920'ye taşırmadan sığdırıp ortadan kırpar."""
    resim = Image.open(yol).convert("RGB")
    oran = max(W / resim.width, H / resim.height)
    resim = resim.resize((max(W, round(resim.width * oran)), max(H, round(resim.height * oran))), Image.LANCZOS)
    x, y = (resim.width - W) // 2, (resim.height - H) // 2
    return resim.crop((x, y, x + W, y + H))


def _izgaraya_sigdir(yol, oran=0.8):
    """Kapağı küçültüp ortalar: profil ızgarasının 3:4 kesiminde yazılar kesilmesin.
    Boşluklar aynı görselin büyütülmüş, bulanık ve karartılmış hâliyle dolar."""
    tam = _doldur(yol)
    zemin = tam.resize((W // 8, H // 8)).filter(ImageFilter.GaussianBlur(6)).resize((W, H), Image.BICUBIC)
    zemin = Image.blend(zemin, Image.new("RGB", (W, H), (0, 0, 0)), 0.45)
    kucuk = tam.resize((int(W * oran), int(H * oran)), Image.LANCZOS)
    golge = Image.new("L", (W, H), 0)
    ImageDraw.Draw(golge).rectangle(((W - kucuk.width) // 2 - 10, (H - kucuk.height) // 2 - 10,
                                     (W + kucuk.width) // 2 + 10, (H + kucuk.height) // 2 + 10), fill=170)
    zemin.paste((0, 0, 0), (0, 0), golge.filter(ImageFilter.GaussianBlur(24)))
    zemin.paste(kucuk, ((W - kucuk.width) // 2, (H - kucuk.height) // 2))
    return zemin


def _arka_planli(zemin_fn):
    """Sayfa sahibi yalnızca arka plan verdiyse çizim zemin yerine o kullanılır (yazılar okunsun diye karartılır)."""
    def sar(vurgu, merkez_y):
        if not _ARKA:
            return zemin_fn(vurgu, merkez_y)
        z = _doldur(_ARKA).convert("RGBA")
        perde = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(perde)
        for y in range(H):
            d.line([(0, y), (W, y)], fill=(0, 0, 0, int(150 * max(0.25, 1 - y / 1100))))
        z.alpha_composite(perde)
        return z
    return sar


_ARKA = None
_zemin = _arka_planli(_zemin)


def kapak_yap(senaryo, senaryo_yolu=""):
    global _ARKA
    hazir = _hazir_gorsel(senaryo_yolu) if senaryo_yolu else None
    if hazir:  # sayfa sahibinin hazırladığı yazılı kapak
        return _izgaraya_sigdir(hazir) if senaryo.get("kapak_sigdir") else _doldur(hazir)
    _ARKA = _hazir_gorsel(senaryo_yolu, "-arka") if senaryo_yolu else None
    if senaryo.get("seri") == "kafa":
        return kapak_kafa(senaryo)
    seri = c.SERILER.get(senaryo.get("seri"), {})
    vurgu = seri.get("renk", c.TURUNCU_MARKA)
    if senaryo.get("seri") == "kafa":
        vurgu = c.KIRMIZI
    kapak = senaryo.get("kapak") or {}
    satirlar = [buyuk(s) for s in kapak.get("satirlar", [])]
    if not satirlar:
        satirlar = [buyuk(s) for s in c.satirlara_sar(senaryo["baslik"], 150, 900)]
    vurgulu = set(kapak.get("vurgu", [len(satirlar) - 1]))

    gorsel, merkez = _gorsel(senaryo, vurgu)
    z = _zemin(vurgu, merkez)
    z.alpha_composite(gorsel, (0, GORSEL_UST))

    # büyük yazı: genişliğe ve 280–960 alanına sığacak kadar büyük
    satirlar = satirlar[:4]
    boyutlar = []
    for satir in satirlar:
        boyut = 240
        while boyut > 90 and _font(boyut).getlength(satir) > 980:
            boyut -= 6
        boyutlar.append(boyut)
    toplam = sum(boyutlar) * 1.06
    if toplam > YAZI_ALT - YAZI_UST:
        oran = (YAZI_ALT - YAZI_UST) / toplam
        boyutlar = [int(b * oran) for b in boyutlar]
    y = YAZI_UST + max(0, (YAZI_ALT - YAZI_UST - sum(boyutlar) * 1.06) / 2)
    for i, (satir, boyut) in enumerate(zip(satirlar, boyutlar)):
        if i in vurgulu:
            resim = _yazi_satiri(satir, boyut, (255, 214, 90), (255, 110, 10), (90, 10, 0), 16)
        else:
            resim = _yazi_satiri(satir, boyut, (255, 255, 255), (196, 202, 214), (150, 18, 18), 16)
        resim = _bosluklu(resim, 40)
        golge = Image.new("RGBA", resim.size, (0, 0, 0, 0))
        golge.putalpha(resim.getchannel("A").filter(ImageFilter.GaussianBlur(14)).point(lambda v: int(v * 0.85)))
        z.alpha_composite(golge, (W // 2 - resim.width // 2 + 8, int(y) + 12 - 40))
        z.alpha_composite(resim, (W // 2 - resim.width // 2, int(y) - 40))
        y += boyut * 1.06
    # ok: yazıdan görsele doğru
    if senaryo.get("seri") != "kafa":
        ok = _ok(300, (255, 200, 40), aci=-28)
        yer = (W - ok.width - 30, GORSEL_UST - 40)
        z.alpha_composite(_parilti(ok, vurgu, 16, 1.4), yer)
        z.alpha_composite(ok, yer)
    # seri etiketi ve logo
    rozet = c.seri_rozeti(senaryo.get("seri"), 34)
    if rozet:
        z.alpha_composite(rozet, (W // 2 - rozet.width // 2, 200))
    logo = c.logo(300)
    z.alpha_composite(logo, (W // 2 - logo.width // 2, 1690 - logo.height // 2))
    return _vinyet(z)


if __name__ == "__main__":
    senaryo = json.load(open(sys.argv[1], encoding="utf-8"))
    cikti = sys.argv[2] if len(sys.argv) > 2 else os.path.join("cikti", os.path.splitext(os.path.basename(sys.argv[1]))[0] + ".jpg")
    os.makedirs(os.path.dirname(cikti) or ".", exist_ok=True)
    kapak_yap(senaryo, sys.argv[1]).save(cikti, quality=92)
    print(f"kapak: {cikti}")
