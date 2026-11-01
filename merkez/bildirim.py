"""Sahibe bildirim = GitHub issue (ek servis/secret yok; GitHub bildirimi sahibe gider). Aynı başlık açıkken tekrar açılmaz."""
from .github_deposu import HttpHata


def issue_ac(istek, depo, baslik, govde, etiket="uyari"):
    """True: yeni açıldı, False: zaten açıktı. Etiket yoksa GitHub oluşturur (yazma yetkisiyle)."""
    d, j = istek("GET", f"/repos/{depo}/issues?state=open&labels={etiket}&per_page=100")
    if d != 200:
        raise HttpHata(d)
    if any(i.get("title") == baslik for i in j if isinstance(j, list)):
        return False
    d, _ = istek("POST", f"/repos/{depo}/issues", {"title": baslik, "body": govde, "labels": [etiket]})
    if d != 201:
        raise HttpHata(d)
    return True
