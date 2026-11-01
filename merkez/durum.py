"""Yayın durum makinesi ve kayıt şeması (kayitlar/<marka>/yayin/<YYYYAAGG-N>.json)."""
import copy

from .hata import GecersizGecis

PLANLANDI, YAYINLANIYOR, YAYINLANDI = "PLANLANDI", "YAYINLANIYOR", "YAYINLANDI"
BASARISIZ, PUBLISH_UNKNOWN, ATLANDI = "BASARISIZ", "PUBLISH_UNKNOWN", "ATLANDI"
DURUMLAR = (PLANLANDI, YAYINLANIYOR, YAYINLANDI, BASARISIZ, PUBLISH_UNKNOWN, ATLANDI)
TERMINAL = (YAYINLANDI, ATLANDI)

IZINLI = {
    PLANLANDI: {YAYINLANIYOR, ATLANDI},
    YAYINLANIYOR: {YAYINLANDI, BASARISIZ, PUBLISH_UNKNOWN, ATLANDI},
    BASARISIZ: {YAYINLANIYOR},
    PUBLISH_UNKNOWN: {YAYINLANDI, BASARISIZ},
    YAYINLANDI: set(),
    ATLANDI: set(),
}

YASAK_ANAHTARLAR = {"token", "access_token", "secret", "password", "parola", "anahtar", "authorization"}
DOGRULAMA = {None, "dogrudan", "container_status", "sahip"}


def yeni_kayit(slot, zaman_iso, sahip_run_id=None):
    return {
        "sema": 1,
        "id": slot.id,
        "marka": slot.marka,
        "slot": {"planlanan": slot.planlanan.isoformat(),
                 "pencere_bitis": slot.pencere_bitis.isoformat(), "sira": slot.sira},
        "durum": PLANLANDI,
        "icerik": {"senaryo_id": None, "surum": None, "video_yolu": None, "video_sha256": None},
        "kilit": {"ref": f"refs/kilit/{slot.marka}/{slot.id}", "sahip": None, "alindi": None, "ttl_bitis": None},
        "deneme": 0,
        "instagram": {"container_id": None, "media_id": None, "publish_istendi": None, "dogrulama": None},
        "hata": {"kod": None, "sinif": None, "ozet": None},
        "gecmis": [{"zaman": zaman_iso, "durum": PLANLANDI, "run_id": sahip_run_id, "not": ""}],
        "olcum": {"claude_cagri": 0, "claude_token": 0, "sure_sn": None, "dry_run": False},
        "sahip_karari": None,
    }


def gecis(kayit, yeni, zaman_iso, run_id=None, not_="", azami_deneme=2,
          dogrulama=None, sahip_karari=None):
    """Kuralları uygulayıp YENİ bir kayıt döndürür; girdiyi değiştirmez."""
    eski = kayit["durum"]
    if yeni not in IZINLI.get(eski, set()):
        raise GecersizGecis(f"{eski} -> {yeni} izinli değil")
    ig = kayit["instagram"]
    if eski == BASARISIZ and yeni == YAYINLANIYOR and kayit["deneme"] >= azami_deneme:
        raise GecersizGecis("deneme hakkı bitti")
    if yeni == ATLANDI and ig["publish_istendi"]:
        raise GecersizGecis("media_publish istenmiş kayıt ATLANDI olamaz")
    if eski == PUBLISH_UNKNOWN:
        if yeni == YAYINLANDI and dogrulama not in ("container_status", "sahip"):
            raise GecersizGecis("PUBLISH_UNKNOWN -> YAYINLANDI yalnız kesin doğrulama veya sahip kararıyla")
        if yeni == BASARISIZ and not sahip_karari:
            raise GecersizGecis("PUBLISH_UNKNOWN -> BASARISIZ için sahip_karari zorunlu")
    yk = copy.deepcopy(kayit)
    yk["durum"] = yeni
    if yeni == YAYINLANIYOR:
        yk["deneme"] += 1
    if dogrulama:
        yk["instagram"]["dogrulama"] = dogrulama
    if sahip_karari:
        yk["sahip_karari"] = sahip_karari
    yk["gecmis"].append({"zaman": zaman_iso, "durum": yeni, "run_id": run_id, "not": not_})
    return yk


def dogrula_kayit(kayit):
    """Şema hatalarının listesini döndürür (boşsa geçerli)."""
    hatalar = []
    for k in ("sema", "id", "marka", "slot", "durum", "icerik", "kilit", "deneme",
              "instagram", "hata", "gecmis", "olcum", "sahip_karari"):
        if k not in kayit:
            hatalar.append(f"eksik alan: {k}")
    if hatalar:
        return hatalar
    if kayit["durum"] not in DURUMLAR:
        hatalar.append("bilinmeyen durum")
    if kayit["instagram"].get("dogrulama") not in DOGRULAMA:
        hatalar.append("geçersiz dogrulama")
    if kayit["olcum"].get("claude_cagri") != 0 or kayit["olcum"].get("claude_token") != 0:
        hatalar.append("Aşama 1'de claude_cagri/claude_token 0 olmalı")
    if not kayit["gecmis"] or kayit["gecmis"][-1]["durum"] != kayit["durum"]:
        hatalar.append("gecmis son kaydı durumla uyuşmuyor")

    def tara(o, yol=""):
        if isinstance(o, dict):
            for k, v in o.items():
                if k.lower() in YASAK_ANAHTARLAR:
                    hatalar.append(f"gizli değer olabilecek anahtar: {yol}{k}")
                tara(v, f"{yol}{k}.")
        elif isinstance(o, list):
            for v in o:
                tara(v, yol)
    tara(kayit)
    return hatalar
