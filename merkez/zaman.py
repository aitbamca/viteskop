"""Slot kimliği ve pencere hesabı. Tüm hesaplar marka saat diliminde (varsayılan Europe/Istanbul)."""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

@dataclass(frozen=True)
class Slot:
    marka: str
    id: str          # YYYYAAGG-N
    sira: int        # günün N'inci slotu (1'den başlar)
    planlanan: datetime
    pencere_bitis: datetime

    def pencere_icinde(self, simdi):
        return self.planlanan <= simdi <= self.pencere_bitis


def slot_id(gun, sira):
    return f"{gun:%Y%m%d}-{sira}"


def gunun_slotlari(cfg, gun):
    gunler = cfg.get("yayin_gunleri")  # None = her gün; aksi: weekday listesi (0=Pzt..6=Paz)
    if gunler is not None and gun.weekday() not in gunler:
        return []
    tz = ZoneInfo(cfg["saat_dilimi"])
    tol = timedelta(minutes=cfg["tolerans_dk"])
    cikti = []
    for sira, hhmm in enumerate(cfg["slotlar"], start=1):
        sa, dk = (int(x) for x in hhmm.split(":"))
        plan = datetime(gun.year, gun.month, gun.day, sa, dk, tzinfo=tz)
        cikti.append(Slot(cfg["marka"], slot_id(gun, sira), sira, plan, plan + tol))
    return cikti


def yerel_gun(cfg, simdi):
    return simdi.astimezone(ZoneInfo(cfg["saat_dilimi"])).date()


def son_slotlar(cfg, simdi, geri_bakis_gun=1):
    """Dün (geri bakış) + bugünün slotları, kronolojik."""
    bugun = yerel_gun(cfg, simdi)
    slotlar = []
    for g in range(geri_bakis_gun, -1, -1):
        slotlar += gunun_slotlari(cfg, bugun - timedelta(days=g))
    return slotlar
