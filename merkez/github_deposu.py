"""GitHub REST üzerinden RefDeposu. Birim testlerde SAHTE taşıma ile çalışır; gerçek API'ye yalnızca
onaylı doğrulama betiği (merkez/dogrulama/github_kilit_dogrulama.py) dokunur.

[DOĞRULANACAK varsayımlar]
  V1 özel ad alanı (refs/kilit/*, refs/video/*, refs/hesap/*) POST /git/refs ile oluşturulabilir
  V2 var olan ref için POST /git/refs → 422
  V3 tek dosyalı ağaçlı commit POST /git/commits ile kurulabilir (blob + ağaç; BOŞ ağaç 422 verir — gerçek testte görüldü)
  V4 PATCH /git/refs/{ref} {"force":false}: ref başka bir commit'e ilerlemişse (yeni commit torunu değilse) → 422
  V5 DELETE /git/refs/{ref} → 204
Herhangi biri başarısızsa yedek: kilit dalı + sha koşullu Contents PUT (409 çakışma).
"""
import json
import time
import urllib.error
import urllib.request


class HttpHata(Exception):
    def __init__(self, durum, govde=""):
        super().__init__(f"HTTP {durum}")
        self.durum, self.govde = durum, govde


def urllib_tasima(token_getir):
    """Gerçek taşıma: token yalnız bellekte, hiçbir yere yazılmaz/loglanmaz."""
    def istek(yontem, yol, govde=None):
        req = urllib.request.Request("https://api.github.com" + yol, method=yontem,
                                     data=None if govde is None else json.dumps(govde).encode(),
                                     headers={"Authorization": f"Bearer {token_getir()}",
                                              "Accept": "application/vnd.github+json",
                                              "X-GitHub-Api-Version": "2022-11-28"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                b = r.read()
                return r.status, (json.loads(b) if b else {})
        except urllib.error.HTTPError as e:
            return e.code, {}
    return istek


class GitHubRefDeposu:
    """UYARI: ilerlet() (PATCH force:false) gerçek GitHub'da bayat sha'yı güvenilir reddetmedi (V4 KALDI, 2026-11-01).
    Yalnız create-only (V1/V2 GEÇTİ) güvenlidir; üretimde GitHubIcerikRefDeposu kullanılır."""

    def __init__(self, depo, istek):
        """depo: 'owner/repo'; istek(yontem, yol, govde) -> (durum, json)."""
        self.depo, self.istek = depo, istek
        self._bos_agac = None

    def _yol(self, p):
        return f"/repos/{self.depo}/git/{p}"

    def _agac(self):
        """Kilit commit'inin ağacı: tek dosyalı gerçek ağaç. (GİRİŞ: GitHub BOŞ ağaç oluşturmayı 422 ile reddeder;
        ilk gerçek testte (2026-11-01) bulundu, V3 varsayımı bu yüzden değişti.)"""
        if self._bos_agac is None:
            d, b = self.istek("POST", self._yol("blobs"), {"content": "kilit", "encoding": "utf-8"})
            if d != 201:
                raise HttpHata(d)
            d, j = self.istek("POST", self._yol("trees"), {"tree": [{"path": "kilit", "mode": "100644", "type": "blob", "sha": b["sha"]}]})
            if d != 201:
                raise HttpHata(d)
            self._bos_agac = j["sha"]
        return self._bos_agac

    def _commit(self, icerik, ebeveyn=None):
        g = {"message": json.dumps(icerik, sort_keys=True), "tree": self._agac(),
             "parents": [ebeveyn] if ebeveyn else []}
        d, j = self.istek("POST", self._yol("commits"), g)
        if d != 201:
            raise HttpHata(d)
        return j["sha"]

    @staticmethod
    def _kisa(ref):
        assert ref.startswith("refs/")
        return ref[len("refs/"):]

    def olustur(self, ref, icerik):
        sha = self._commit(icerik)
        d, _ = self.istek("POST", self._yol("refs"), {"ref": ref, "sha": sha})
        if d == 201:
            return sha
        if d == 422:
            return None
        raise HttpHata(d)

    def oku(self, ref):
        d, j = self.istek("GET", self._yol("ref/" + self._kisa(ref)))
        if d == 404:
            return None
        if d != 200:
            raise HttpHata(d)
        sha = j["object"]["sha"]
        d, c = self.istek("GET", self._yol("commits/" + sha))
        if d != 200:
            raise HttpHata(d)
        return sha, json.loads(c["message"])

    def ilerlet(self, ref, beklenen_sha, icerik):
        sha = self._commit(icerik, ebeveyn=beklenen_sha)
        d, _ = self.istek("PATCH", self._yol("refs/" + self._kisa(ref)), {"sha": sha, "force": False})
        if d == 200:
            return sha
        if d in (422, 404):
            return None
        raise HttpHata(d)

    def sil(self, ref, beklenen_sha):
        v = self.oku(ref)  # GitHub koşullu silme sunmaz; sahip kontrolü üst katmanda
        if v is None or v[0] != beklenen_sha:
            return False
        d, _ = self.istek("DELETE", self._yol("refs/" + self._kisa(ref)))
        return d == 204


class GitHubIcerikRefDeposu:
    """RefDeposu arayüzü, Contents API (sha koşullu PUT/DELETE) üzerinden — ÜRETİM arka ucu.
    Neden: gerçek GitHub'da V4 (PATCH force:false ile bayat sha reddi) KALDI; V1/V2 (create-only), V6/V7 (Contents
    koşullu yazma, 8 eşzamanlı yazıdan 1 kazanan) GEÇTİ. Kilit = `kilitler/<ad>.json` dosyası (marka deposunun kayıt dalında).
    sha = blob sha. oku -> (sha, icerik)."""

    def __init__(self, depo, dal, istek, kok="kilitler"):
        from .github_kayit import GitHubKayitDeposu
        self.k = GitHubKayitDeposu(depo, dal, istek)
        self.kok = kok

    def _yol(self, ref):
        return f"{self.kok}/{ref[len('refs/'):] if ref.startswith('refs/') else ref}.json"

    def olustur(self, ref, icerik):
        return self.k.yaz_yol(self._yol(ref), icerik, None, f"kilit olustur {ref}")

    def oku(self, ref):
        v = self.k.oku_yol(self._yol(ref))
        return None if v is None else (v[1], v[0])

    def ilerlet(self, ref, beklenen_sha, icerik):
        return self.k.yaz_yol(self._yol(ref), icerik, beklenen_sha, f"kilit guncelle {ref}")

    def sil(self, ref, beklenen_sha):
        yol = self._yol(ref)
        for n in range(6):
            d, _ = self.k.istek("DELETE", f"/repos/{self.k.depo}/contents/{yol}",
                                {"message": f"kilit sil {ref}", "sha": beklenen_sha, "branch": self.k.dal})
            if d == 200:
                return True
            if d in (404,):
                return False
            if d in (409, 422):
                mevcut = self.k.oku_yol(yol)
                if mevcut is None or mevcut[1] != beklenen_sha:
                    return False
                time.sleep(0.15 * (n + 1))
                continue
            raise HttpHata(d)
        raise HttpHata(409, "dal sürekli ilerliyor")
