"""Marka deposundaki yayin.yml'in giriş noktası.

  --kuru   : Instagram/Pages çağrısı YOK (DryInstagram); kilit ve kayıtlar test ad alanında
             (refs/test/..., kayitlar/<marka>/test/yayin/). INSTAGRAM_TOKEN/MEDYA_TOKEN bu modda hiç verilmez.
  --canli  : gerçek yayın. Yalnız workflow `canli_onay=EVET-CANLI` ile çağrılır.
Çıkış kodu: 0 = beklenen/zararsız sonuç (YAYINLANDI, ATLANDI, DUPLICATE_SKIP ...); 1 = BASARISIZ / PUBLISH_UNKNOWN /
beklenmeyen hata (iş akışı kırmızı olur → sahibe GitHub bildirimi gider).
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

from . import marka_sema, yayin_calistir
from .bildirim import issue_ac
from .github_deposu import GitHubIcerikRefDeposu, urllib_tasima
from .github_kayit import GitHubKayitDeposu
from .instagram_istemci import GraphIstemci
from .kilit import Kilitci
from .video_secici import adaylar
from .zaman import son_slotlar

SORUN = {"BASARISIZ", "PUBLISH_UNKNOWN", "DENEME_BITTI"}


def slot_bul(cfg, slot_id, simdi):
    for s in son_slotlar(cfg, simdi, geri_bakis_gun=2):
        if s.id == slot_id:
            return s
    raise SystemExit(f"bilinmeyen/eski slot: {slot_id}")  # dispatcher'ın ürettiği kimlikler dışında iş yapılmaz


def _gh(*a):
    return subprocess.run(["gh", *a], capture_output=True, text=True)


def hazir_adlar(depo, istek):
    d, j = istek("GET", f"/repos/{depo}/releases/tags/hazir")
    if d != 200:
        return set()
    return {x["name"] for x in j.get("assets", [])}


class MedyaAdresi:
    """Videoyu `hazir` release'inden indirip Pages adresine koyar (mevcut medya_yayinla.sh mantığı).
    cfg["kapak_uretici"] == "kapak.py" ise (viteskop) önce kapak üretilir; üretilemezse videodan kare (mevcut akışla aynı)."""

    def __init__(self, cfg):
        self.kapak_uretici = cfg.get("kapak_uretici")

    def __call__(self, video):
        ad = os.path.basename(video.yol)[:-5] + ".mp4"
        r = _gh("release", "download", "hazir", "-p", ad, "-D", "cikti", "--clobber")
        if r.returncode:
            raise yayin_calistir.IgKesinHata("VIDEO_INDIRILEMEDI", ad)
        argv = ["bash", "medya_yayinla.sh", "koy", f"cikti/{ad}"]
        if self.kapak_uretici:
            kapak = f"cikti/{ad[:-4]}.jpg"
            if subprocess.run([sys.executable, self.kapak_uretici, video.yol, kapak], capture_output=True).returncode == 0:
                argv.append(kapak)
        r = subprocess.run(argv, capture_output=True, text=True)
        satirlar = [x for x in r.stdout.splitlines() if x.strip()]
        if r.returncode or not satirlar:
            raise yayin_calistir.IgKesinHata("PAGES_ADRESI_YOK", "")
        return (satirlar[0], satirlar[1] if len(satirlar) > 1 else None)


def sonlandir(sonuc, video, canli):
    """Yayın sonrası temizlik. UNKNOWN'da HİÇBİR ŞEY silinmez (manuel inceleme için video ve varlık kalır)."""
    if not canli or video is None:
        return
    if sonuc == "YAYINLANDI":
        subprocess.run(["bash", "medya_yayinla.sh", "temizle"], capture_output=True)
        ad = os.path.basename(video.yol)[:-5] + ".mp4"
        _gh("release", "delete-asset", "hazir", ad, "-y")
        with open("yayinlananlar.txt", "a", encoding="utf-8") as f:  # mevcut defter biçimi (istatistik uyumu)
            f.write(f"{os.path.basename(video.yol)}\t{datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ}\t{video.medya_id}\n")
    elif sonuc in ("BASARISIZ", "DENEME_BITTI"):
        subprocess.run(["bash", "medya_yayinla.sh", "temizle"], capture_output=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--marka", required=True)
    ap.add_argument("--slot-id", required=True)
    ap.add_argument("--mod", choices=["yayin", "kapanis"], default="yayin")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--kuru", action="store_true")
    g.add_argument("--canli", action="store_true")
    a = ap.parse_args(argv)
    cfg = marka_sema.yukle("markalar")[a.marka]
    simdi = datetime.now(timezone.utc)
    slot = slot_bul(cfg, a.slot_id, simdi)
    depo_adi = os.environ["GITHUB_REPOSITORY"]
    gh = urllib_tasima(lambda: os.environ["GITHUB_TOKEN"])
    kuru = a.kuru
    kilitci = Kilitci(GitHubIcerikRefDeposu(depo_adi, cfg["kayit_dali"], gh), kok="refs/test" if kuru else "refs")
    kayitlar = GitHubKayitDeposu(depo_adi, cfg["kayit_dali"], gh, test=kuru)
    run = os.environ.get("GITHUB_RUN_ID", "0")
    sahip = f"run{run}-a{os.environ.get('GITHUB_RUN_ATTEMPT', '1')}"
    if kuru:
        ig = yayin_calistir.DryInstagram()
        adaylari = lambda: adaylar(".", None)
    else:
        import instagram  # mevcut modül: yalnız aciklama_yaz kullanılır
        ig = GraphIstemci(lambda: os.environ["INSTAGRAM_TOKEN"], MedyaAdresi(cfg))
        hz = hazir_adlar(depo_adi, gh)
        adaylari = lambda: adaylar(".", hz, instagram.aciklama_yaz)
    secilen = {}

    def adaylari_izle():
        for v in adaylari():
            secilen["v"] = v
            yield v
    bildir = lambda m, s, tur, ozet: (not kuru) and issue_ac(
        gh, depo_adi, f"[UYARI] {m} {s} {tur}", f"Slot {s}: {tur} {ozet}. Elle inceleme gerekir.")
    ctx = yayin_calistir.Ctx(cfg, slot, kilitci, kayitlar, ig, adaylari_izle, lambda: datetime.now(timezone.utc),
                             sahip, bildirim=bildir, uyku=__import__("time").sleep, dry_run=kuru)
    sonuc = yayin_calistir.kapanis(ctx) if a.mod == "kapanis" else yayin_calistir.calistir(ctx)
    k = kayitlar.oku(cfg["marka"], slot.id)
    video = None
    if k and k[0]["icerik"]["video_sha256"]:
        video = yayin_calistir.Video(k[0]["icerik"]["video_sha256"], k[0]["icerik"]["video_yolu"])
        video.medya_id = k[0]["instagram"]["media_id"]
    sonlandir(sonuc, video, a.canli)
    print(json.dumps({"marka": a.marka, "slot": slot.id, "sonuc": sonuc, "kuru": kuru}, ensure_ascii=False))
    return 1 if sonuc in SORUN else 0


if __name__ == "__main__":
    sys.exit(main())
