"""markalar/*.json doğrulayıcı. Gizli değer içermez; yalnızca yapılandırma."""
import json
import os
import re
from zoneinfo import ZoneInfo

YASAK = {"token", "access_token", "secret", "password", "parola", "anahtar", "authorization"}


def dogrula(cfg):
    h = []
    if cfg.get("sema") != 1:
        h.append("sema 1 olmalı")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", str(cfg.get("marka", ""))):
        h.append("marka adı [a-z0-9-] olmalı")
    if not isinstance(cfg.get("aktif"), bool):
        h.append("aktif bool olmalı")
    try:
        ZoneInfo(cfg.get("saat_dilimi", ""))
    except Exception:
        h.append("geçersiz saat_dilimi")
    gl = cfg.get("yayin_gunleri")
    if gl is not None and (not isinstance(gl, list) or not gl or sorted(set(gl)) != sorted(gl)
                           or not all(isinstance(x, int) and 0 <= x <= 6 for x in gl)):
        h.append("yayin_gunleri 0..6 arası benzersiz tamsayı listesi olmalı")
    sl = cfg.get("slotlar")
    if cfg.get("manuel_video") is True and sl == []:
        pass  # manuel video markası (örn. cosicosas): yayın slotu zamanlayıcıda yok
    elif not isinstance(sl, list) or not sl or not all(isinstance(x, str) and re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", x) for x in sl):
        h.append("slotlar HH:MM listesi olmalı")
    elif sl and sl != sorted(set(sl)):
        h.append("slotlar artan ve benzersiz olmalı")
    for alan, lo, hi in (("tolerans_dk", 5, 60), ("kilit_ttl_dk", 5, 60),
                         ("hesap_kilit_ttl_dk", 3, 30), ("azami_deneme", 1, 2),
                         ("hesap_bekleme_dk", 0, 30)):
        v = cfg.get(alan)
        if not isinstance(v, int) or isinstance(v, bool) or not lo <= v <= hi:
            h.append(f"{alan} {lo}..{hi} arası tamsayı olmalı")
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", str(cfg.get("kayit_deposu", ""))):
        h.append("kayit_deposu owner/repo olmalı")
    if cfg.get("kapak_uretici") not in (None, "kapak.py"):
        h.append("kapak_uretici null veya 'kapak.py' olmalı")
    ab = cfg.get("aktif_baslangic")
    if ab is None:
        if cfg.get("aktif") is True:
            h.append("aktif:true iken aktif_baslangic (saat dilimli ISO zaman) zorunlu")
    else:
        try:
            from datetime import datetime as _dt
            if _dt.fromisoformat(ab).tzinfo is None:
                h.append("aktif_baslangic saat dilimi içermeli")
        except (ValueError, TypeError):
            h.append("aktif_baslangic geçersiz ISO zaman")
    for alan in ("dispatch_token_env", "okuma_token_env"):
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", str(cfg.get(alan, ""))):
            h.append(f"{alan} bir ortam değişkeni ADI olmalı (değer değil)")
    for alan in ("kayit_dali", "yayin_workflow", "token_kontrol_workflow"):
        if not re.fullmatch(r"[\w./-]+", str(cfg.get(alan, ""))):
            h.append(f"{alan} geçersiz")
    ig = cfg.get("instagram")
    if not isinstance(ig, dict) or not isinstance(ig.get("environment"), str):
        h.append("instagram.environment (ad) gerekli")
    def tara(o, yol=""):
        if isinstance(o, dict):
            for k, v in o.items():
                if k.lower() in YASAK:
                    h.append(f"gizli değer olabilecek anahtar: {yol}{k}")
                tara(v, f"{yol}{k}.")
    tara(cfg)
    return h


def haftalik_video(cfg):
    gun = len(cfg["yayin_gunleri"]) if cfg.get("yayin_gunleri") is not None else 7
    return len(cfg["slotlar"]) * gun


def yukle(klasor):
    """`_` ile başlamayan *.json dosyalarını doğrulayıp {marka: cfg} döndürür; hata varsa ValueError."""
    markalar, hatalar = {}, []
    for ad in sorted(os.listdir(klasor)):
        if not ad.endswith(".json") or ad.startswith("_"):
            continue
        with open(os.path.join(klasor, ad), encoding="utf-8") as f:
            cfg = json.load(f)
        e = dogrula(cfg)
        if e:
            hatalar += [f"{ad}: {x}" for x in e]
        elif cfg["marka"] + ".json" != ad:
            hatalar.append(f"{ad}: dosya adı marka ile eşleşmeli")
        else:
            markalar[cfg["marka"]] = cfg
    if hatalar:
        raise ValueError("; ".join(hatalar))
    return markalar
