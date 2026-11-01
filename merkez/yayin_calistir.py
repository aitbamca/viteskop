"""Marka yayin.yml'in çekirdeği. Instagram istemcisi enjekte edilir (Aşama 1'de gerçek API yok).

Akış: pencere → slot kilidi → kayıt → video seçimi+video kilidi → hesap muteksi → YAYINLANIYOR →
container → (pencere) → publish_istendi kaydı → media_publish.
Kurallar (sahip kararları):
  * media_publish sonrası belirsizlik → PUBLISH_UNKNOWN; OTOMATİK TEKRAR YOK; yalnız container 'PUBLISHED'
    ise YAYINLANDI; 'FINISHED' yayınlanmadığın kanıtı SAYILMAZ.
  * Slot kilidi hiçbir durumda bırakılmaz. Video kilidi yalnız kesin yayınlanmadıysa bırakılır.
  * Yeniden deneme: yalnız kesin hata + pencere içi + azami_deneme.
"""
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Callable, Iterable

from . import durum as D
from .hata import IgBelirsizHata, IgKesinHata

MAX_POLL = 24
POLL_SN = 5
GERI_CEKILME_SN = (30, 90)


class KayitCakismasi(Exception):
    pass


@dataclass
class Video:
    sha256: str          # kararlı video kimliği (kilit anahtarı); gerçek akışta senaryo dosya adı
    yol: str
    senaryo_id: str = None
    surum: int = None
    aciklama: str = ""   # Instagram açıklaması (kayda yazılmaz)
    kapak_ms: int = 2500
    medya_id: str = None  # yayın sonrası Instagram medya kimliği (defter için; kayda ayrıca yazılır)


@dataclass
class Ctx:
    cfg: dict
    slot: object
    kilitci: object
    kayitlar: object
    ig: object
    video_adaylari: Callable[[], Iterable[Video]]
    simdi: Callable
    sahip: str                      # örn. "run123-a1"
    bildirim: Callable = lambda marka, slot_id, tur, ozet: None
    uyku: Callable = lambda sn: None
    dry_run: bool = False
    baslangic: object = field(default=None)


class DryInstagram:
    """Dry-run: ağ çağrısı yok."""
    def container_olustur(self, video): return "dry-container"
    def container_durum(self, cid): return "FINISHED"
    def yayinla(self, cid): return "dry-media"


class _Defter:
    def __init__(self, c, kayit, ver):
        self.c, self.kayit, self.ver = c, kayit, ver

    def kaydet(self):
        k = self.kayit
        yeni = self.c.kayitlar.yaz(k["marka"], k["id"], k, self.ver)
        if yeni is None:
            raise KayitCakismasi(k["id"])
        self.ver = yeni

    def gecis(self, yeni, **kw):
        self.kayit = D.gecis(self.kayit, yeni, self.c.simdi().isoformat(), self.c.sahip,
                             azami_deneme=self.c.cfg["azami_deneme"], **kw)
        self.kaydet()

    def guncelle(self, fn):
        fn(self.kayit)
        self.kaydet()

    def hata(self, kod, sinif, ozet=""):
        def f(k):
            k["hata"] = {"kod": kod, "sinif": sinif, "ozet": (ozet or "")[:200]}
        self.guncelle(f)


def _kayit_yarat(c):
    k = D.yeni_kayit(c.slot, c.simdi().isoformat(), c.sahip)
    k["olcum"]["dry_run"] = c.dry_run
    k["kilit"]["ref"] = c.kilitci.slot_ref(c.slot.marka, c.slot.id)
    ver = c.kayitlar.yaz(c.slot.marka, c.slot.id, k, None)
    if ver is None:
        raise KayitCakismasi(c.slot.id)
    return _Defter(c, k, ver)


def kapanis(c):
    """Pencere geçmiş slot: kayıt yok/PLANLANDI ise ATLANDI yazar (telafi yok). Başka durumlara dokunmaz."""
    try:
        okunan = c.kayitlar.oku(c.slot.marka, c.slot.id)
        if okunan is None:
            d = _kayit_yarat(c)
        elif okunan[0]["durum"] == D.PLANLANDI:
            d = _Defter(c, okunan[0], okunan[1])
        else:
            return "KAPANIS_GEREKSIZ"
        d.gecis(D.ATLANDI, not_="PENCERE_GECTI")
        return D.ATLANDI
    except KayitCakismasi:
        return "CAKISMA"


def calistir(c):
    try:
        return _calistir(c)
    except KayitCakismasi:
        return "CAKISMA"  # başka bir çalışma/kapanış aynı kaydı değiştirdi; yayın yapılmadan çıkıldı


def _calistir(c):
    cfg, slot, kl = c.cfg, c.slot, c.kilitci
    simdi = c.simdi()
    if simdi < slot.planlanan:
        return "HENUZ_DEGIL"
    if simdi > slot.pencere_bitis:
        return kapanis(c)

    # 1) slot kilidi
    durum, sha, mevcut = kl.slot_al(slot.marka, slot.id, c.sahip, cfg["kilit_ttl_dk"])
    okunan = c.kayitlar.oku(slot.marka, slot.id)
    if durum == "DOLU":
        k = okunan[0] if okunan else None
        yeni_sha = None
        if mevcut and kl.suresi_dolmus(mevcut):
            yeni_sha = kl.slot_devral(slot.marka, slot.id, sha, c.sahip, cfg["kilit_ttl_dk"],
                                      k["durum"] if k else D.PLANLANDI,
                                      k["instagram"]["publish_istendi"] if k else None)
        if not yeni_sha:
            return "DUPLICATE_SKIP"

    # 2) kayıt
    if okunan is None:
        d = _kayit_yarat(c)
    else:
        d = _Defter(c, okunan[0], okunan[1])
        if d.kayit["durum"] == D.YAYINLANIYOR:  # devralınan, yayına gitmemiş yarım çalışma
            d.gecis(D.BASARISIZ, not_="YARIDA_KALDI")
        if d.kayit["durum"] not in (D.PLANLANDI, D.BASARISIZ):
            return "DUPLICATE_SKIP"
        if d.kayit["durum"] == D.BASARISIZ and d.kayit["deneme"] >= cfg["azami_deneme"]:
            return "DENEME_BITTI"

    # 3) video + video kilidi
    video = None
    sha_kayit = d.kayit["icerik"]["video_sha256"]
    if sha_kayit:  # devralınan kayıt: aynı video, kilit zaten slot adına
        video = Video(sha_kayit, d.kayit["icerik"]["video_yolu"])
    else:
        for aday in c.video_adaylari():
            if kl.video_al(slot.marka, aday.sha256, slot.id):
                video = aday
                break
        if video is None:
            d.gecis(D.ATLANDI, not_="STOK_YOK")
            c.bildirim(slot.marka, slot.id, "STOK_YOK", "")
            return D.ATLANDI

        def f(k):
            k["icerik"] = {"senaryo_id": video.senaryo_id, "surum": video.surum,
                           "video_yolu": video.yol, "video_sha256": video.sha256}
            k["kilit"].update({"sahip": c.sahip, "alindi": simdi.isoformat()})
        d.guncelle(f)

    def kesin_yayinlanmadi_birak():
        kl.video_birak(slot.marka, video.sha256, slot.id)

    # 4) hesap muteksi
    bitis = min(slot.pencere_bitis, simdi + timedelta(minutes=cfg["hesap_bekleme_dk"]))
    hs = None
    while True:
        hs = kl.hesap_al(slot.marka, c.sahip, cfg["hesap_kilit_ttl_dk"])
        if hs:
            break
        if c.simdi() >= bitis:
            d.gecis(D.ATLANDI, not_="HESAP_MESGUL")
            kesin_yayinlanmadi_birak()
            return D.ATLANDI
        c.uyku(15)
    try:
        return _yayinla(c, d, video, kesin_yayinlanmadi_birak)
    finally:
        kl.hesap_birak(slot.marka, c.sahip, hs)


def _yayinla(c, d, video, birak):
    cfg, slot, ig = c.cfg, c.slot, c.ig
    d.gecis(D.YAYINLANIYOR)
    while True:
        if c.simdi() > slot.pencere_bitis:
            d.gecis(D.ATLANDI, not_="PENCERE_GECTI")  # publish_istendi yok → güvenli
            birak()
            return D.ATLANDI
        def temiz(k):
            k["instagram"].update({"container_id": None, "media_id": None, "publish_istendi": None})
        d.guncelle(temiz)
        try:
            cid = ig.container_olustur(video)
            d.guncelle(lambda k: k["instagram"].__setitem__("container_id", cid))
            for _ in range(MAX_POLL):
                st = ig.container_durum(cid)
                if st == "FINISHED":
                    break
                if st in ("ERROR", "EXPIRED"):
                    raise IgKesinHata(f"CONTAINER_{st}")
                if c.simdi() > slot.pencere_bitis:
                    break
                c.uyku(POLL_SN)
            else:
                raise IgKesinHata("CONTAINER_ZAMAN_ASIMI")
            if st != "FINISHED":
                d.gecis(D.ATLANDI, not_="PENCERE_GECTI")  # container var ama publish istenmedi
                birak()
                return D.ATLANDI
            if c.simdi() > slot.pencere_bitis:
                d.gecis(D.ATLANDI, not_="PENCERE_GECTI")
                birak()
                return D.ATLANDI
        except (IgKesinHata, IgBelirsizHata) as e:  # publish öncesi: hiçbir şey yayınlanmadı
            if _basarisiz_ve_tekrar(c, d, e):
                continue
            birak()
            return D.BASARISIZ

        # --- geri dönüşsüz nokta: önce kaydet, sonra publish ---
        d.guncelle(lambda k: k["instagram"].__setitem__("publish_istendi", c.simdi().isoformat()))
        try:
            media_id = ig.yayinla(cid)
        except IgKesinHata as e:
            if _basarisiz_ve_tekrar(c, d, e):
                continue
            birak()
            return D.BASARISIZ
        except IgBelirsizHata as e:
            return _belirsiz(c, d, cid, e)
        d.guncelle(lambda k: k["instagram"].update({"media_id": media_id, "dogrulama": "dogrudan"}))
        d.gecis(D.YAYINLANDI, dogrulama="dogrudan")
        return D.YAYINLANDI


def _basarisiz_ve_tekrar(c, d, e):
    d.hata(e.kod, "kesin" if isinstance(e, IgKesinHata) else "belirsiz-publish-oncesi", e.ozet)
    d.gecis(D.BASARISIZ, not_=e.kod)
    n = d.kayit["deneme"]
    if n >= c.cfg["azami_deneme"]:
        return False
    bekle = GERI_CEKILME_SN[min(n - 1, len(GERI_CEKILME_SN) - 1)]
    c.uyku(bekle)
    if c.simdi() > c.slot.pencere_bitis:
        return False
    d.gecis(D.YAYINLANIYOR)
    return True


def _belirsiz(c, d, cid, e):
    d.hata(e.kod, "belirsiz", e.ozet)
    d.gecis(D.PUBLISH_UNKNOWN, not_=e.kod)
    try:
        if c.ig.container_durum(cid) == "PUBLISHED":  # tek izinli kesin doğrulama
            d.gecis(D.YAYINLANDI, dogrulama="container_status")
            return D.YAYINLANDI
    except (IgKesinHata, IgBelirsizHata):
        pass
    c.bildirim(c.slot.marka, c.slot.id, "PUBLISH_UNKNOWN", e.kod)
    return D.PUBLISH_UNKNOWN
