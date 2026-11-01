"""Kayıt deposu — GitHub Contents API (marka deposundaki `kayitlar` dalı). Sürüm = blob sha.
Dal yoksa 404 verir: dalı oluşturmak AYRI ONAY gerektiren bir yazma işlemidir (bu modül oluşturmaz).
  yaz(): sha vermezsen yalnız dosya YOKSA oluşturur; sha verirsen yalnız sha güncelse günceller.
         409/422 → çakışma (None). Başka hata → HttpHata.
[DOĞRULANACAK] 422 (create varken sha'sız PUT) ve 409 (bayat sha) davranışı — onaylı doğrulamada.
"""
import base64
import json
import time

from .github_deposu import HttpHata

DENEME = 6  # 409 hem "bayat sha" hem "dal başka yazıyla ilerledi" anlamına gelir: ikisini ayırmak için yeniden okunur


class GitHubKayitDeposu:
    def __init__(self, depo, dal, istek, kok="kayitlar", test=False):
        self.depo, self.dal, self.istek, self.kok, self.test = depo, dal, istek, kok, test

    def yol(self, marka, kid):
        return f"{self.kok}/{marka}/{'test/' if self.test else ''}yayin/{kid}.json"

    def oku_yol(self, yol):
        d, j = self.istek("GET", f"/repos/{self.depo}/contents/{yol}?ref={self.dal}")
        if d == 404:
            return None
        if d != 200:
            raise HttpHata(d)
        return json.loads(base64.b64decode(j["content"])), j["sha"]

    def yaz_yol(self, yol, nesne, beklenen_surum, mesaj):
        """Koşullu yazma. Dönüş: yeni sha | None (gerçek çakışma: dosya var/sürüm bayat).
        409 ayrımı: sha hâlâ beklenen sürümse dal başka bir yazıyla ilerlemiştir → yeniden denenir (sahte çakışma değil)."""
        g = {"message": mesaj, "branch": self.dal,
             "content": base64.b64encode(json.dumps(nesne, ensure_ascii=False, indent=2, sort_keys=True).encode()).decode()}
        if beklenen_surum:
            g["sha"] = beklenen_surum
        for n in range(DENEME):
            d, j = self.istek("PUT", f"/repos/{self.depo}/contents/{yol}", g)
            if d in (200, 201):
                return j["content"]["sha"]
            if d in (409, 422):
                mevcut = self.oku_yol(yol)
                if beklenen_surum is None and mevcut is not None:
                    return None          # dosya zaten var
                if beklenen_surum is not None and (mevcut is None or mevcut[1] != beklenen_surum):
                    return None          # sürüm bayat / dosya yok
                time.sleep(0.15 * (n + 1))  # dal ilerledi ama bizim dosyamız değişmedi → tekrar dene
                continue
            raise HttpHata(d)
        raise HttpHata(409, "dal sürekli ilerliyor")

    def oku(self, marka, kid):
        return self.oku_yol(self.yol(marka, kid))

    def yaz(self, marka, kid, kayit, beklenen_surum):
        return self.yaz_yol(self.yol(marka, kid), kayit, beklenen_surum, f"yayin kaydi {marka} {kid} {kayit['durum']}")
