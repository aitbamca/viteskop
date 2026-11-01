"""Yayın kayıt deposu: sürüm koşullu yazma (optimistic concurrency).
Gerçek uygulama: github_kayit.py (Contents API, sha koşullu PUT). yaz() yeni sürümü döndürür, çakışmada None."""
import hashlib
import json
import os
import tempfile


def surum(kayit):
    return hashlib.sha256(json.dumps(kayit, sort_keys=True).encode()).hexdigest()


class BellekKayitDeposu:
    def __init__(self):
        import threading
        self._d = {}
        self._k = threading.Lock()

    def oku(self, marka, kid):
        v = self._d.get((marka, kid))
        return None if v is None else (json.loads(json.dumps(v)), surum(v))

    def yaz(self, marka, kid, kayit, beklenen_surum):
        with self._k:
            mevcut = self._d.get((marka, kid))
            if (mevcut is None) != (beklenen_surum is None):
                return None
            if mevcut is not None and surum(mevcut) != beklenen_surum:
                return None
            self._d[(marka, kid)] = json.loads(json.dumps(kayit))
            return surum(kayit)

    def hepsi(self, marka):
        return {k[1]: v for k, v in self._d.items() if k[0] == marka}


class DosyaKayitDeposu:
    """kayitlar/<marka>/yayin/<id>.json düzeni (tek süreç içi; atomik rename)."""

    def __init__(self, kok):
        self.kok = kok

    def _yol(self, marka, kid):
        return os.path.join(self.kok, marka, "yayin", f"{kid}.json")

    def oku(self, marka, kid):
        try:
            with open(self._yol(marka, kid), encoding="utf-8") as f:
                k = json.load(f)
        except FileNotFoundError:
            return None
        return k, surum(k)

    def yaz(self, marka, kid, kayit, beklenen_surum):
        mevcut = self.oku(marka, kid)
        if (mevcut is None) != (beklenen_surum is None):
            return None
        if mevcut is not None and mevcut[1] != beklenen_surum:
            return None
        yol = self._yol(marka, kid)
        os.makedirs(os.path.dirname(yol), exist_ok=True)
        fd, gecici = tempfile.mkstemp(dir=os.path.dirname(yol))
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(kayit, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(gecici, yol)
        return surum(kayit)
