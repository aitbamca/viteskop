"""Instagram ve kilit katmanı hata sınıfları."""


class IgKesinHata(Exception):
    """Gönderinin YAYINLANMADIĞI kesin olan hata (doğrulama/yetki/medya, 4xx, container ERROR/EXPIRED)."""

    def __init__(self, kod, ozet=""):
        super().__init__(f"{kod}: {ozet}")
        self.kod = kod
        self.ozet = ozet


class IgBelirsizHata(Exception):
    """media_publish sonucu bilinmiyor (zaman aşımı, 5xx, ağ kopması, çözümsüz yanıt)."""

    def __init__(self, kod, ozet=""):
        super().__init__(f"{kod}: {ozet}")
        self.kod = kod
        self.ozet = ozet


class GecersizGecis(ValueError):
    """Durum makinesi kuralına aykırı geçiş."""
