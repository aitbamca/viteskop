"""Atomik ref kilitleri.

Soyutlama `RefDeposu`: olustur (yalnız yoksa), oku, ilerlet (karşılaştır-ve-değiştir), sil.
Uygulamalar: BellekDeposu (hızlı birim test), GitYerelDeposu (gerçek git ref atomikliği, çok süreçli
testler), GitHubRefDeposu (merkez/github_deposu.py; gerçek API, yalnız onaylı doğrulamada).

Üç kilit türü:
  * slot kilidi   refs/kilit/<marka>/<slotid>       kalıcı; otomatik silinmez
  * video kilidi  refs/video/<marka>/<sha256>       yalnız kesin-yayınlanmadı durumunda silinir
  * hesap muteksi refs/hesap/<marka>                kısa ömürlü; silinmez, 'serbest' durumuna CAS ile geçer
"""
import json
import subprocess
import threading
from datetime import datetime, timedelta, timezone

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def _iso(dt):
    return dt.isoformat()


class BellekDeposu:
    def __init__(self):
        self._r = {}
        self._n = 0
        self._k = threading.Lock()

    def _yeni_sha(self):
        self._n += 1
        return f"{self._n:040x}"

    def olustur(self, ref, icerik):
        with self._k:
            if ref in self._r:
                return None
            sha = self._yeni_sha()
            self._r[ref] = (sha, json.loads(json.dumps(icerik)))
            return sha

    def oku(self, ref):
        with self._k:
            v = self._r.get(ref)
            return None if v is None else (v[0], json.loads(json.dumps(v[1])))

    def ilerlet(self, ref, beklenen_sha, icerik):
        with self._k:
            v = self._r.get(ref)
            if v is None or v[0] != beklenen_sha:
                return None
            sha = self._yeni_sha()
            self._r[ref] = (sha, json.loads(json.dumps(icerik)))
            return sha

    def sil(self, ref, beklenen_sha):
        with self._k:
            v = self._r.get(ref)
            if v is None or v[0] != beklenen_sha:
                return False
            del self._r[ref]
            return True


class GitYerelDeposu:
    """Yerel bare git deposu: ref işlemleri `git update-ref` ile (ref kilit dosyası = gerçek atomiklik).
    Ref, boş ağaçlı bir 'kilit commit'ine işaret eder; mesaj JSON'dur; ilerletme = torun commit.
    """

    def __init__(self, yol, baslat=True):
        self.yol = yol
        if baslat:
            subprocess.run(["git", "init", "-q", "--bare", yol], check=True)
            self._git("hash-object", "-t", "tree", "-w", "--stdin", girdi=b"")

    def _git(self, *a, girdi=None, kontrol=True):
        env = {"GIT_AUTHOR_NAME": "k", "GIT_AUTHOR_EMAIL": "k@k", "GIT_COMMITTER_NAME": "k",
               "GIT_COMMITTER_EMAIL": "k@k", "PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": "/tmp"}
        return subprocess.run(["git", "-C", self.yol, *a], input=girdi, capture_output=True,
                              env=env, check=kontrol)

    def _commit(self, icerik, ebeveyn=None):
        arg = ["commit-tree", EMPTY_TREE, "-m", json.dumps(icerik, sort_keys=True)]
        if ebeveyn:
            arg += ["-p", ebeveyn]
        return self._git(*arg).stdout.decode().strip()

    def olustur(self, ref, icerik):
        sha = self._commit(icerik)
        r = self._git("update-ref", ref, sha, "0" * 40, kontrol=False)
        return sha if r.returncode == 0 else None

    def oku(self, ref):
        r = self._git("rev-parse", "--verify", "-q", ref, kontrol=False)
        if r.returncode != 0:
            return None
        sha = r.stdout.decode().strip()
        msg = self._git("log", "-1", "--format=%B", sha).stdout.decode().strip()
        return sha, json.loads(msg)

    def ilerlet(self, ref, beklenen_sha, icerik):
        sha = self._commit(icerik, ebeveyn=beklenen_sha)
        r = self._git("update-ref", ref, sha, beklenen_sha, kontrol=False)
        return sha if r.returncode == 0 else None

    def sil(self, ref, beklenen_sha):
        return self._git("update-ref", "-d", ref, beklenen_sha, kontrol=False).returncode == 0


class Kilitci:
    """Kilit mantığı; zaman `simdi()` ile enjekte edilir (test için)."""

    def __init__(self, depo, simdi=lambda: datetime.now(timezone.utc), kok="refs"):
        """kok: üretimde "refs"; dry-run'da "refs/test" (üretim kilitlerinden tamamen ayrı ad alanı)."""
        self.depo = depo
        self.simdi = simdi
        self.kok = kok

    # --- ortak ---
    def _icerik(self, sahip, ttl_dk, amac, durum="tutuluyor"):
        t = self.simdi()
        return {"sahip": sahip, "alindi": _iso(t), "ttl_bitis": _iso(t + timedelta(minutes=ttl_dk)),
                "durum": durum, "amac": amac}

    def suresi_dolmus(self, icerik):
        return datetime.fromisoformat(icerik["ttl_bitis"]) <= self.simdi()

    # --- slot kilidi ---
    def slot_ref(self, marka, slot_id):
        return f"{self.kok}/kilit/{marka}/{slot_id}"

    def slot_al(self, marka, slot_id, sahip, ttl_dk):
        ref = self.slot_ref(marka, slot_id)
        sha = self.depo.olustur(ref, self._icerik(sahip, ttl_dk, "slot"))
        if sha:
            return ("ALINDI", sha, None)
        v = self.depo.oku(ref)
        return ("DOLU", v[0] if v else None, v[1] if v else None)

    @staticmethod
    def devralma_uygun(kayit_durumu, publish_istendi):
        """Süresi dolmuş slot kilidi yalnızca hiçbir şey yayınlanmış olamayacaksa devralınabilir."""
        if kayit_durumu == "PLANLANDI":
            return True
        if kayit_durumu == "YAYINLANIYOR" and not publish_istendi:
            return True
        return False

    def slot_devral(self, marka, slot_id, beklenen_sha, sahip, ttl_dk, kayit_durumu, publish_istendi):
        """Süresi dolmuş ve devralmaya uygun kilidi CAS ile devralır; aksi halde None."""
        if not self.devralma_uygun(kayit_durumu, publish_istendi):
            return None
        ref = self.slot_ref(marka, slot_id)
        v = self.depo.oku(ref)
        if v is None or v[0] != beklenen_sha or not self.suresi_dolmus(v[1]):
            return None
        return self.depo.ilerlet(ref, beklenen_sha, self._icerik(sahip, ttl_dk, "slot"))

    def slot_yenile(self, marka, slot_id, sha, sahip, ttl_dk):
        ref = self.slot_ref(marka, slot_id)
        v = self.depo.oku(ref)
        if v is None or v[0] != sha or v[1]["sahip"] != sahip:
            return None
        return self.depo.ilerlet(ref, sha, self._icerik(sahip, ttl_dk, "slot"))

    def slot_sahibi_mi(self, marka, slot_id, sahip):
        v = self.depo.oku(self.slot_ref(marka, slot_id))
        return bool(v and v[1]["sahip"] == sahip)

    # --- video kilidi ---
    def video_ref(self, marka, sha256):
        return f"{self.kok}/video/{marka}/{sha256}"

    def video_al(self, marka, sha256, sahip):
        sha = self.depo.olustur(self.video_ref(marka, sha256), self._icerik(sahip, 24 * 60 * 365, "video"))
        return sha

    def video_birak(self, marka, sha256, sahip):
        """Yalnız kesin yayınlanmadı bilindiğinde çağrılmalı; sahibi değilse dokunmaz."""
        ref = self.video_ref(marka, sha256)
        v = self.depo.oku(ref)
        if v is None or v[1]["sahip"] != sahip:
            return False
        return self.depo.sil(ref, v[0])

    # --- hesap muteksi (aynı Instagram hesabında eşzamanlı yayın oluşturmayı önler) ---
    def hesap_ref(self, marka):
        return f"{self.kok}/hesap/{marka}"

    def hesap_al(self, marka, sahip, ttl_dk):
        ref = self.hesap_ref(marka)
        yeni = self._icerik(sahip, ttl_dk, "hesap")
        sha = self.depo.olustur(ref, yeni)
        if sha:
            return sha
        v = self.depo.oku(ref)
        if v is None:
            return None
        if v[1]["durum"] == "serbest" or self.suresi_dolmus(v[1]):
            return self.depo.ilerlet(ref, v[0], yeni)  # CAS: iki aday varsa biri kazanır
        return None

    def hesap_birak(self, marka, sahip, sha):
        """Silmez; CAS ile 'serbest' yapar. Süre dolup başkası devraldıysa sha uyuşmaz → dokunmaz."""
        ref = self.hesap_ref(marka)
        v = self.depo.oku(ref)
        if v is None or v[0] != sha or v[1]["sahip"] != sahip:
            return False
        serbest = dict(v[1], durum="serbest", ttl_bitis=_iso(self.simdi()))
        return self.depo.ilerlet(ref, sha, serbest) is not None
