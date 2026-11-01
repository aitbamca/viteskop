"""Instagram token süre uyarısı (otomatik yenileme YOK; sahip kararı 2026-11-01)."""
ESIKLER = (14, 7, 3, 1)


def uyari_seviyesi(kalan_gun):
    """Ulaşılan en dar eşik (14/7/3/1) veya süre dolduysa 0; uyarı gerekmiyorsa None."""
    if kalan_gun <= 0:
        return 0
    for e in sorted(ESIKLER):
        if kalan_gun <= e:
            return e
    return None


def yeni_uyari_gerekli(kalan_gun, son_uyari):
    """Aynı eşik için tekrar uyarı üretmez. son_uyari: daha önce bildirilen seviye veya None."""
    s = uyari_seviyesi(kalan_gun)
    if s is None:
        return None
    if son_uyari is not None and s >= son_uyari:
        return None
    return s
