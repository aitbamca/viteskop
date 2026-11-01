"""Instagram token süre kontrolü (günde bir kez). Otomatik yenileme YOK.
Kaynak: marka deposunun `kayitlar` dalında kayitlar/<marka>/token.json  {"bitis": "YYYY-MM-DD", "son_uyari": null}
(sahibin girdiği bitiş tarihi; token değeri asla yazılmaz). Eşik 14/7/3/1/0 → issue; aynı eşik tekrar uyarmaz."""
import argparse
import os
import sys
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from . import marka_sema
from .bildirim import issue_ac
from .github_deposu import urllib_tasima
from .github_kayit import GitHubKayitDeposu
from .token_kontrol import yeni_uyari_gerekli


def kontrol(cfg, depo, bugun, uyar):
    yol = f"{depo.kok}/{cfg['marka']}/token.json"
    v = depo.oku_yol(yol)
    if v is None:
        uyar(f"[UYARI] {cfg['marka']} token bitiş bilgisi yok",
             f"`{yol}` dosyası yok. Sahip `bitis` (YYYY-MM-DD) girmeli. Token değerini YAZMAYIN.")
        return {"marka": cfg["marka"], "durum": "BITIS_BILGISI_YOK"}
    nesne, sha = v
    kalan = (date.fromisoformat(nesne["bitis"]) - bugun).days
    seviye = yeni_uyari_gerekli(kalan, nesne.get("son_uyari"))
    if seviye is not None:
        etiket = "SURESI DOLDU" if seviye == 0 else f"{kalan} gün kaldı"
        uyar(f"[UYARI] {cfg['marka']} Instagram token: {etiket}",
             f"Bitiş: {nesne['bitis']}. Token elle yenilenmeli (otomatik yenileme kapalı). Yenileyince `bitis` güncellenir ve `son_uyari` sıfırlanır.")
        nesne["son_uyari"] = seviye
        depo.yaz_yol(yol, nesne, sha, f"token uyari seviyesi {seviye}")
    return {"marka": cfg["marka"], "kalan_gun": kalan, "uyari": seviye}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--marka", required=True)
    ap.add_argument("--canli", action="store_true")
    a = ap.parse_args(argv)
    cfg = marka_sema.yukle("markalar")[a.marka]
    istek = urllib_tasima(lambda: os.environ["GITHUB_TOKEN"])
    depo = GitHubKayitDeposu(os.environ.get("GITHUB_REPOSITORY", cfg["kayit_deposu"]), cfg["kayit_dali"], istek)
    bugun = datetime.now(timezone.utc).astimezone(ZoneInfo(cfg["saat_dilimi"])).date()
    uyar = (lambda b, g: issue_ac(istek, os.environ["GITHUB_REPOSITORY"], b, g)) if a.canli else \
           (lambda b, g: print("KURU uyarı:", b))
    print(kontrol(cfg, depo, bugun, uyar))
    return 0


if __name__ == "__main__":
    sys.exit(main())
