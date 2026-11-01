"""Instagram Graph (Instagram girişli API) istemcisi — Reels yayını.

Mevcut `instagram.py`'den FARKLARI (bilinçli):
  * HİÇBİR iç yeniden deneme yok (eski istemci media_publish'i 5xx'te tekrar deniyordu → çift paylaşım riski).
    Yeniden deneme/karar yalnızca `yayin_calistir`'dadır.
  * Hata sınıflaması: media_publish için HTTP 4xx → IgKesinHata (yayınlanmadı kesin);
    5xx, zaman aşımı, ağ kopması, çözümsüz/eksik yanıt → IgBelirsizHata (yayınlandı mı bilinmiyor).
  * Token yalnız bellekte; hata mesajına URL/parametre/token girmez, yalnız API'nin hata kodu ve kısa özeti.
Taşıma (transport) enjekte edilir: testte ağ yok.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from .hata import IgBelirsizHata, IgKesinHata

SURUM = os.environ.get("IG_API_SURUMU") or "v23.0"
TABAN = f"https://graph.instagram.com/{SURUM}"


class AgHatasi(Exception):
    """Taşıma katmanı: zaman aşımı/bağlantı hatası (HTTP yanıtı alınamadı)."""


def urllib_tasima(zaman_asimi=120):
    def istek(yontem, yol, params):
        url = TABAN + yol
        veri = None
        if yontem == "GET":
            url += "?" + urllib.parse.urlencode(params)
        else:
            veri = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(url, data=veri, method=yontem)
        try:
            with urllib.request.urlopen(req, timeout=zaman_asimi) as r:
                govde = r.read()
                return r.status, govde
        except urllib.error.HTTPError as e:
            return e.code, e.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            raise AgHatasi("ag") from None  # özgün hata URL içerebilir; atılır
    return istek


def _ozet(govde):
    """API hata gövdesinden yalnız güvenli alanlar (kod/tür/kısa mesaj)."""
    try:
        e = json.loads(govde).get("error", {})
        return f"api_kod={e.get('code')} alt={e.get('error_subcode')} tur={e.get('type')} {str(e.get('message', ''))[:120]}"
    except (ValueError, AttributeError, TypeError):
        return "ayrıştırılamadı"


class GraphIstemci:
    def __init__(self, token_getir, adres_hazirla, tasima=None):
        """token_getir(): token'ı döndürür (bellekte tutulmaz).
        adres_hazirla(video) -> herkese açık video URL'si (Pages); Instagram videoyu bu adresten çeker."""
        self._token = token_getir
        self._adres = adres_hazirla
        self._t = tasima or urllib_tasima()
        self._kullanici = None

    def _cagri(self, yontem, yol, params, yayin=False):
        p = dict(params, access_token=self._token())
        try:
            durum, govde = self._t(yontem, yol, p)
        except AgHatasi:
            raise IgBelirsizHata("AG_HATASI", "zaman aşımı/bağlantı") from None
        if 200 <= durum < 300:
            try:
                return json.loads(govde or b"{}")
            except ValueError:
                raise IgBelirsizHata("YANIT_COZUMSUZ", f"HTTP {durum}") from None
        if durum >= 500:
            raise IgBelirsizHata(f"HTTP_{durum}", _ozet(govde))
        raise IgKesinHata(f"HTTP_{durum}", _ozet(govde))

    def _kullanici_id(self):
        if self._kullanici is None:
            self._kullanici = self._cagri("GET", "/me", {"fields": "user_id"})["user_id"]
        return self._kullanici

    def container_olustur(self, video):
        adres = self._adres(video)  # str (video) veya (video_url, kapak_url|None) — viteskop kapak.py akışı
        video_url, kapak_url = adres if isinstance(adres, tuple) else (adres, None)
        alanlar = {"media_type": "REELS", "video_url": video_url, "caption": video.aciklama, "share_to_feed": "true"}
        if kapak_url:
            alanlar["cover_url"] = kapak_url
        else:
            alanlar["thumb_offset"] = str(int(video.kapak_ms))
        yanit = self._cagri("POST", f"/{self._kullanici_id()}/media", alanlar)
        if "id" not in yanit:
            raise IgBelirsizHata("CONTAINER_ID_YOK", "")
        return yanit["id"]

    def container_durum(self, cid):
        return self._cagri("GET", f"/{cid}", {"fields": "status_code"}).get("status_code", "")

    def yayinla(self, cid):
        yanit = self._cagri("POST", f"/{self._kullanici_id()}/media_publish", {"creation_id": cid}, yayin=True)
        if "id" not in yanit:
            raise IgBelirsizHata("MEDIA_ID_YOK", "")  # 2xx ama id yok: yayınlanmış olabilir
        return yanit["id"]
