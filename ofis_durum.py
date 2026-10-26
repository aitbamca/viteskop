"""Sanal ofis için durum özeti: depodaki dosyalardan JSON üretir (ekrana yazar).

Kullanım: python ofis_durum.py > /tmp/durum.json
Ofis müdürü ajanı bu çıktıyı ofis sayfasının veritabanına yazar (durum/ozet belgesi).
"""
import csv
import datetime
import glob
import json
import os

TR = datetime.timezone(datetime.timedelta(hours=3))
PAYLASIM_SAATLERI = ["12:30", "20:00"]
URETIM_SAATLERI = ["10:23", "15:23"]


def satirlar(yol):
    return [s.strip() for s in open(yol, encoding="utf-8")] if os.path.exists(yol) else []


def csv_oku(yol):
    return list(csv.DictReader(open(yol, encoding="utf-8"))) if os.path.exists(yol) else []


def baslik(yol):
    try:
        d = json.load(open(yol, encoding="utf-8"))
        return d.get("baslik", os.path.basename(yol)), d.get("seri") or d.get("tema") or "otomatik", d.get("editor", {})
    except (OSError, ValueError):
        return os.path.basename(yol), "?", {}


def tr_saat(iso_utc):
    try:
        z = datetime.datetime.strptime(iso_utc, "%Y-%m-%dT%H:%MZ").replace(tzinfo=datetime.timezone.utc)
    except ValueError:
        return iso_utc
    return z.astimezone(TR).strftime("%-d %b %H:%M").replace("Oct", "Ekim").replace("Nov", "Kasım").replace("Dec", "Aralık")


TEMA_ADI = {"garaj": "garaj", "showroom": "showroom", "otoyol": "otoyol", "gece_sehir": "gece şehir", "gosterge": "gösterge",
            "kafa": "Kafa Kafaya", "bakim": "Bakım Saati", "ariza": "Arıza Alarmı", "parca": "Parça Rehberi"}


def sonraki_paylasim(simdi, sira=0):
    """sira'ncı sıradaki videonun paylaşılacağı zaman (0 = ilk boş paylaşım saati)."""
    gun, saatler = 0, [s for s in PAYLASIM_SAATLERI if simdi.strftime("%H:%M") < s]
    while sira >= len(saatler):
        sira -= len(saatler)
        gun, saatler = gun + 1, list(PAYLASIM_SAATLERI)
    return f"{['bugün', 'yarın'][gun] if gun < 2 else f'{gun} gün sonra'} {saatler[sira]}"


def main():
    simdi = datetime.datetime.now(TR)
    uretilen = list(dict.fromkeys(s for s in satirlar("yapilanlar.txt") if s))
    yayinlanan = {}
    for s in satirlar("yayinlananlar.txt"):
        parca = s.split("\t")
        if len(parca) >= 2:
            yayinlanan[parca[0]] = parca[1]
    paylasim_sirasi = [a for a in uretilen if a not in yayinlanan and os.path.exists(f"senaryolar/{a}")]

    videolar = []
    for yol in sorted(glob.glob("taslaklar/*.json")):
        b, tema, _ = baslik(yol)
        videolar.append({"baslik": b, "adim": 1, "not": f"Taslak · editör kontrolünde · seri: {TEMA_ADI.get(tema, tema)}"})
    for yol in sorted(glob.glob("taslaklar/reddedilen/*.json"))[-2:]:
        b, _, ed = baslik(yol)
        videolar.append({"baslik": b, "adim": 1, "uyari": True, "not": "Editör reddetti: " + str(ed.get("neden", ""))[:90]})
    for yol in sorted(glob.glob("senaryolar/*.json")):
        ad = os.path.basename(yol)
        if ad in yayinlanan:
            continue
        b, tema, _ = baslik(yol)
        if ad in uretilen:
            sira = paylasim_sirasi.index(ad) if ad in paylasim_sirasi else 0
            videolar.append({"baslik": b, "adim": 4, "not": f"Hazır · seri: {TEMA_ADI.get(tema, tema)} · yayın: {sonraki_paylasim(simdi, sira)}"})
        else:
            videolar.append({"baslik": b, "adim": 2, "not": f"Editör onayladı · video üretimi bekliyor ({' · '.join(URETIM_SAATLERI)})"})
    yayinda = sorted(yayinlanan.items(), key=lambda x: x[1], reverse=True)
    for ad, zaman in yayinda[:4]:
        b, tema, _ = baslik(f"senaryolar/{ad}")
        videolar.append({"baslik": b, "adim": 5, "not": f"Instagram'da yayında · {tr_saat(zaman)} · seri: {TEMA_ADI.get(tema, tema)}"})

    hesap = csv_oku("veriler/hesap.csv")
    istat = csv_oku("veriler/videolar.csv")
    son_istat = {}
    for s in istat:
        son_istat[s.get("dosya")] = s  # her video için en son satır
    izlenme = sum(int(float(s.get("views") or 0)) for s in son_istat.values()) if son_istat else None
    takipci = int(hesap[-1]["takipci"]) if hesap and hesap[-1].get("takipci") not in (None, "") else 0
    en_iyi = max(son_istat.values(), key=lambda s: float(s.get("views") or 0), default=None)

    bekleyen = sum(1 for v in videolar if v["adim"] == 2)
    hazir = sum(1 for v in videolar if v["adim"] == 4)
    siradaki = baslik(f"senaryolar/{paylasim_sirasi[0]}")[0] if paylasim_sirasi else None
    makineler = [
        {"key": "yapimci", "ad": "Yapımcı", "gorev": "Onaylanan senaryoyu sesli, altyazılı videoya çevirir", "ikon": "film",
         "durum": "bekliyor" if bekleyen else "hazir",
         "ekran": f"{bekleyen} video üretim bekliyor. Gemini (Iapetus) sesiyle üretilecek." if bekleyen else f"Bekleyen iş yok. {hazir} video yayına hazır.",
         "zaman": "Onaydan sonra · " + " · ".join(URETIM_SAATLERI)},
        {"key": "yayinci", "ad": "Yayıncı", "gorev": "Sıradaki videoyu Instagram'a Reels olarak koyar", "ikon": "gonder", "durum": "hazir",
         "ekran": f"Sıradaki: {siradaki} ({sonraki_paylasim(simdi)})" if siradaki else "Paylaşılacak hazır video yok, yenileri üretiliyor.",
         "zaman": " · ".join(PAYLASIM_SAATLERI)},
        {"key": "veri", "ad": "Veri toplayıcı", "gorev": "İzlenme, beğeni, kaydetme ve takipçi sayılarını toplar", "ikon": "veri", "durum": "hazir",
         "ekran": (f"Son ölçüm {hesap[-1]['tarih']}: {takipci} takipçi, toplam {izlenme or 0} izlenme." if hesap else "Instagram bağlanınca her gece ölçülür.")
                  + (f" En çok izlenen: {baslik('senaryolar/' + en_iyi['dosya'])[0]}." if en_iyi and float(en_iyi.get('views') or 0) > 0 else ""),
         "zaman": "Her gece 23:47"},
    ]

    yapilacaklar = []
    raporlar = sorted(glob.glob("raporlar/*.md"))
    if raporlar:
        yapilacaklar.append({"is": "Son raporu oku", "detay": os.path.basename(raporlar[-1]) + " · beğendiğin önerileri numarasıyla onayla."})
    if any(v.get("uyari") for v in videolar):
        yapilacaklar.append({"is": "Reddedilen taslağa göz at", "detay": "Editör bir taslağı reddetti; yazar ertesi gün nedenini okuyup düzeltir."})
    if not yapilacaklar:
        yapilacaklar.append({"is": "Her şey yolunda", "detay": "Sistem kendi dönüyor. Pazartesi raporları gelince burada görünecek."})

    print(json.dumps({
        "guncelleme": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "videolar": videolar,
        "makineler": makineler,
        "instagram": {"takipci": takipci, "gonderi": len(yayinlanan), "izlenme": izlenme,
                      "not": f"Sıradaki Reels: {siradaki} · {sonraki_paylasim(simdi)}" if siradaki else "Sıradaki Reels hazırlanıyor."},
        "yapilacaklar": yapilacaklar,
        "ozet": {"hazir": hazir, "yayinda": len(yayinlanan), "takipci": takipci, "izlenme": izlenme, "siradaki": siradaki},
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
