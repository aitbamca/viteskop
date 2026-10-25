"""Instagram'a Reels paylaşır (Instagram girişli Instagram API).

Kullanım:
  python instagram.py kontrol                         # token çalışıyor mu, hesap bilgisi
  python instagram.py paylas VIDEO_ADRESI SENARYO.json  # herkese açık adresteki videoyu Reels olarak paylaş
  python instagram.py istatistik                      # paylaşılan videoların ve hesabın verilerini veriler/'e ekler

Token INSTAGRAM_TOKEN ortam değişkeninden okunur.
"""
import csv
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SURUM = os.environ.get("IG_API_SURUMU") or "v23.0"
TABAN = f"https://graph.instagram.com/{SURUM}"


def _token():
    token = os.environ.get("INSTAGRAM_TOKEN", "").strip()
    if not token:
        sys.exit("INSTAGRAM_TOKEN tanımlı değil (GitHub → Settings → Secrets and variables → Actions).")
    return token


def _istek(yontem, url, parametreler=None, govde=None, basliklar=None):
    parametreler = dict(parametreler or {})
    if govde is None and yontem == "POST":
        govde = urllib.parse.urlencode(parametreler).encode()
        parametreler = {}
    if parametreler:
        url += "?" + urllib.parse.urlencode(parametreler)
    istek = urllib.request.Request(url, data=govde, method=yontem, headers=basliklar or {})
    try:
        with urllib.request.urlopen(istek, timeout=300) as yanit:
            return json.loads(yanit.read() or b"{}")
    except urllib.error.HTTPError as hata:
        icerik = hata.read().decode(errors="replace")
        try:  # token'ı asla loglara yazma
            icerik = json.dumps(json.loads(icerik).get("error", icerik), ensure_ascii=False)
        except ValueError:
            pass
        raise RuntimeError(f"Instagram API hatası (HTTP {hata.code}): {icerik[:500]}") from None


def hesap():
    return _istek("GET", f"{TABAN}/me", {"fields": "user_id,username,account_type,media_count",
                                          "access_token": _token()})


def aciklama_yaz(senaryo):
    """Türkçe açıklama, altında İngilizcesi, en sonda etiketler."""
    parcalar = [senaryo.get("aciklama") or senaryo["baslik"]]
    ingilizce = senaryo.get("aciklama_en") or senaryo.get("baslik_en")
    if ingilizce:
        parcalar.append("🇬🇧 " + ingilizce)
    if senaryo.get("etiketler"):
        parcalar.append(" ".join(senaryo["etiketler"][:30]))
    return "\n\n".join(parcalar)[:2200]


def reels_paylas(video_adresi, aciklama, kapak_ms=2500):
    """video_adresi: Instagram'ın videoyu çekeceği herkese açık adres (viteskop-medya GitHub Pages)."""
    token = _token()
    kullanici = hesap()["user_id"]

    # 1) Kapsayıcı oluştur: Instagram videoyu adresten kendisi indirir
    kap = _istek("POST", f"{TABAN}/{kullanici}/media", {
        "media_type": "REELS", "video_url": video_adresi, "caption": aciklama,
        "share_to_feed": "true", "thumb_offset": str(int(kapak_ms)), "access_token": token})
    kap_id = kap["id"]

    # 2) Instagram videoyu indirip işlerken bekle
    for _ in range(60):
        durum = _istek("GET", f"{TABAN}/{kap_id}", {"fields": "status_code,status", "access_token": token})
        if durum.get("status_code") == "FINISHED":
            break
        if durum.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram videoyu işleyemedi: {durum}")
        time.sleep(10)
    else:
        raise RuntimeError("Instagram 10 dakikada videoyu işlemeyi bitiremedi.")

    # 3) Yayınla
    return _istek("POST", f"{TABAN}/{kullanici}/media_publish", {"creation_id": kap_id, "access_token": token})["id"]


VIDEO_METRIKLERI = ["views", "reach", "likes", "comments", "shares", "saved", "total_interactions",
                    "ig_reels_avg_watch_time", "ig_reels_video_view_total_time"]


def video_istatistikleri(medya_id):
    """Metrik adları zamanla değişebiliyor: toplu istek olmazsa tek tek dener, olmayanları atlar."""
    token = _token()
    def iste(metrikler):
        yanit = _istek("GET", f"{TABAN}/{medya_id}/insights", {"metric": ",".join(metrikler), "access_token": token})
        return {m["name"]: m["values"][0]["value"] for m in yanit.get("data", []) if m.get("values")}
    try:
        return iste(VIDEO_METRIKLERI)
    except RuntimeError:
        sonuc = {}
        for metrik in VIDEO_METRIKLERI:
            try:
                sonuc.update(iste([metrik]))
            except RuntimeError as hata:
                print(f"  {metrik} alınamadı: {str(hata)[:120]}")
        return sonuc


def _csv_ekle(yol, alanlar, satirlar):
    yeni = not os.path.exists(yol)
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, "a", newline="", encoding="utf-8") as f:
        yazici = csv.DictWriter(f, fieldnames=alanlar, extrasaction="ignore")
        if yeni:
            yazici.writeheader()
        yazici.writerows(satirlar)


def istatistik_topla():
    tarih = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    bilgi = _istek("GET", f"{TABAN}/me", {"fields": "username,followers_count,follows_count,media_count",
                                           "access_token": _token()})
    _csv_ekle("veriler/hesap.csv", ["tarih", "takipci", "takip_edilen", "gonderi"],
              [{"tarih": tarih, "takipci": bilgi.get("followers_count"), "takip_edilen": bilgi.get("follows_count"),
                "gonderi": bilgi.get("media_count")}])
    satirlar = []
    if os.path.exists("yayinlananlar.txt"):
        for satir in open("yayinlananlar.txt", encoding="utf-8"):
            parca = satir.rstrip("\n").split("\t")
            if len(parca) < 3:
                continue
            dosya, yayin, medya = parca[:3]
            try:
                veri = video_istatistikleri(medya)
            except RuntimeError as hata:
                print(f"  {dosya}: {str(hata)[:160]}")
                continue
            satirlar.append({"tarih": tarih, "dosya": dosya, "yayin_zamani": yayin, "medya": medya, **veri})
    _csv_ekle("veriler/videolar.csv", ["tarih", "dosya", "yayin_zamani", "medya"] + VIDEO_METRIKLERI, satirlar)
    return f"{bilgi.get('followers_count')} takipçi, {len(satirlar)} videonun verisi kaydedildi"


if __name__ == "__main__":
    komut = sys.argv[1] if len(sys.argv) > 1 else "kontrol"
    if komut == "kontrol":
        bilgi = hesap()
        try:  # istatistik izni (instagram_business_manage_insights) var mı?
            _istek("GET", f"{TABAN}/me/insights", {"metric": "reach", "period": "day", "access_token": _token()})
            izin = "istatistik izni var"
        except RuntimeError as hata:
            izin = f"istatistik izni YOK ({str(hata)[:120]})"
        print(f"Bağlantı tamam: @{bilgi.get('username')} ({bilgi.get('account_type')}, {bilgi.get('media_count')} gönderi), {izin}")
    elif komut == "paylas":
        video_adresi, senaryo_yolu = sys.argv[2], sys.argv[3]
        senaryo = json.load(open(senaryo_yolu, encoding="utf-8"))
        medya = reels_paylas(video_adresi, aciklama_yaz(senaryo), senaryo.get("kapak_ms", 2500))  # kapak: sorunun büyük göründüğü an
        print(f"paylaşıldı: {os.path.basename(senaryo_yolu)} → medya {medya}")
    elif komut == "istatistik":
        print(istatistik_topla())
    else:
        sys.exit(__doc__)
