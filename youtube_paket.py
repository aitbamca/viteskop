"""Instagram'da yayınlanmış videoları YouTube'a elle yüklemek için tek pakette toplar.

Her video için, yayın anından önceki en yeni "videolar-*" çalışma çıktısındaki sürüm alınır (Instagram'a giden sürüm).
Çıktı: youtube-paket/NN-<ad>.mp4 ve youtube-paket/youtube-metinler.txt (başlık, açıklama, etiketler).
GitHub Actions içinde çalışır (GH_TOKEN ve GITHUB_REPOSITORY gerekir): python youtube_paket.py
"""
import datetime
import io
import json
import os
import subprocess
import sys
import zipfile

DEPO = os.environ["GITHUB_REPOSITORY"]
CIKTI = "youtube-paket"
COCUK = "sosyal-otomasyon" in DEPO  # clufive: YouTube'da "Çocuklar için yapıldı" işaretlenmeli


def gh(*arg, ikili=False):
    return subprocess.run(["gh", *arg], check=True, capture_output=True, text=not ikili).stdout


def zaman(metin):
    return datetime.datetime.strptime(metin.replace("Z", ""), "%Y-%m-%dT%H:%M:%S" if metin.count(":") == 2 else "%Y-%m-%dT%H:%M")


def yayinlananlar():
    son = {}
    for satir in open("yayinlananlar.txt", encoding="utf-8"):
        parca = satir.rstrip("\n").split("\t")
        if len(parca) >= 2:
            son[parca[0]] = zaman(parca[1])  # aynı video iki kez paylaşıldıysa sonuncusu
    return sorted(son.items(), key=lambda x: x[1])


def cikti_listesi():
    sayfa, hepsi = 1, []
    while True:
        veri = json.loads(gh("api", f"repos/{DEPO}/actions/artifacts?per_page=100&page={sayfa}"))
        hepsi += [a for a in veri["artifacts"] if not a["expired"]]
        if len(veri["artifacts"]) < 100:
            return sorted(hepsi, key=lambda a: a["created_at"], reverse=True)
        sayfa += 1


_zipler = {}
def zip_ac(cikti):
    if cikti["id"] not in _zipler:
        _zipler[cikti["id"]] = zipfile.ZipFile(io.BytesIO(gh("api", f"repos/{DEPO}/actions/artifacts/{cikti['id']}/zip", ikili=True)))
    return _zipler[cikti["id"]]


def metin(sira, ad, senaryo):
    baslik = senaryo.get("baslik") or ad
    etiketler = list(senaryo.get("etiketler") or [])
    satirlar = [f"=== {sira:02d} · {ad[:-5]}.mp4 ===",
                f"BAŞLIK: {(baslik + ' #shorts')[:100]}",
                "AÇIKLAMA:", (senaryo.get("aciklama") or baslik), "", " ".join(etiketler[:15]), ""]
    if senaryo.get("baslik_en"):
        satirlar += [f"İNGİLİZCE BAŞLIK (çeviri olarak ekle): {senaryo['baslik_en'][:100]}",
                     f"İNGİLİZCE AÇIKLAMA: {senaryo.get('aciklama_en') or senaryo['baslik_en']}", ""]
    return "\n".join(satirlar)


def main():
    os.makedirs(CIKTI, exist_ok=True)
    ciktilar = cikti_listesi()
    metinler = ["YouTube'a yükleme listesi (yayın sırasıyla).",
                "Kitle ayarı: " + ("ÇOCUKLAR İÇİN YAPILDI (zorunlu)." if COCUK else "Çocuklar için yapılmadı."), ""]
    eksik = []
    for sira, (ad, yayin) in enumerate(yayinlananlar(), 1):
        video = ad[:-5] + ".mp4"
        bulunan = None
        for c in ciktilar:  # yayından önceki en yeni çıktı = Instagram'a giden sürüm
            if zaman(c["created_at"]) > yayin:
                continue
            z = zip_ac(c)
            if video in z.namelist():
                bulunan = z.read(video)
                break
        if not bulunan:
            eksik.append(ad)
            print(f"::warning title=Bulunamadı::{video}")
            continue
        open(os.path.join(CIKTI, f"{sira:02d}-{video}"), "wb").write(bulunan)
        yol = os.path.join("senaryolar", ad)
        senaryo = json.load(open(yol, encoding="utf-8")) if os.path.exists(yol) else {}
        metinler.append(metin(sira, ad, senaryo))
    if eksik:
        metinler.append("Bulunamayanlar (30 günlük saklama süresi dolmuş olabilir): " + ", ".join(eksik))
    open(os.path.join(CIKTI, "youtube-metinler.txt"), "w", encoding="utf-8").write("\n".join(metinler) + "\n")
    print(f"{len(os.listdir(CIKTI)) - 1} video pakete kondu, {len(eksik)} eksik.")


if __name__ == "__main__":
    sys.exit(main())
