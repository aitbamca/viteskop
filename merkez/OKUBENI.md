# merkez/ (sosyal-otomasyon'dan kopya)

Bu klasör `aitbamca/sosyal-otomasyon` deposundaki `merkez/` paketinin YAYIN için gereken alt kümesidir (sürüm: `merkez/SURUM`).
Tek kaynak sosyal-otomasyon'dur; burada elle değişiklik yapılmaz, güncelleme oradan kopyalanır.

Durum: **HAZIR BEKLİYOR** — `markalar/viteskop.json` içinde `aktif:false`; iş akışları yalnız elle tetiklenir (`workflow_dispatch`),
zamanlama yok. Canlı yayın için `dry_run=false` + `canli_onay=EVET-CANLI` + `uretim` Environment'ı gerekir.
Mevcut Viteskop iş akışlarına (instagram.yml, gunluk-video.yml …) dokunulmadı.
