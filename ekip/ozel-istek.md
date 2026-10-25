# ⚡ Özel istek talimatı – Viteskop

Sayfa sahibi program dışında bir konu isteyebilir. İstekler **Viteskop Paneli**'nin veritabanındaki `istek` koleksiyonundadır
(ArtifactData; url: https://claude.ai/artifact/Bbptq64xnkCdhrqCEiowhr). Belge alanları:
`konu`, `not` (isteğe bağlı ayrıntı), `zaman`, `durum` (`bekliyor` → `taslak` → `onaylandi` / `reddedildi`), `taslak`, `senaryo`, `mesaj`.
Özel istek **sıranın en önüne geçer**: onaylanınca `oncelikli.txt`'ye yazılır; video kota müsaitse hemen üretilir ve
ilk boş paylaşım saatinde (planlı videonun yerine) yayınlanır.

## Yazar (⚡ Özel istek rutini)
1. `git pull origin main`. `istek` koleksiyonunda `durum: "bekliyor"` olanları bul (`query`).
2. Her biri için `ekip/yazar.md` kurallarıyla **bir** senaryo yaz (araştır, doğrula, test et):
   `taslaklar/YYYYAAGG-O-kisa-ad.json` (O = özel; aynı gün birden fazlaysa O1, O2) ve JSON'a `"oncelikli": true` ekle.
   Konu Viteskop'a uygun değilse (oto dışı, tehlikeli tavsiye gerektiriyor, doğrulanamıyor) yazma; belgeyi `durum: "reddedildi"`,
   `mesaj`: kısa neden yap.
3. `git add taslaklar/ && git commit -m "Özel istek taslağı: <başlık>" && git push origin main`.
4. İstek belgesini `update`: `{"durum": "taslak", "taslak": "<dosya adı>"}`.
5. Editörü hemen çağır: `fire_trigger` aracın varsa (Claude Code Remote) `trigger_id: "trig_01DtHPp61ca4zYkh73pdaBFv"` ile çalıştır (rutin metninde EDITOR_TETIK_VITESKOP yazıyorsa bu kimliktir).
   Yoksa sorun değil; editör günde iki kez özel istekleri ayrıca kontrol eder.
6. Panel postasına kısa mail (`ekip/iletisim.md`, anahtarın `yazar`): "Özel istek taslağı hazır: <başlık>".

## Editör (⚡ Özel istek kontrolü)
1. `git pull origin main`. `taslaklar/` içinde `"oncelikli": true` olan taslakları bul. Yoksa hiçbir şey yapma, bitir.
2. Her birini `ekip/editor.md`'deki gibi **bağımsız** kontrol et (bilgiyi kendin doğrula, kareye bak).
3. Onay: `editor` alanını ekle, `git mv` ile `senaryolar/`a taşı, dosya adını **`oncelikli.txt`'nin sonuna ekle**, sonra
   `git add -A taslaklar/ senaryolar/ oncelikli.txt && git commit -m "Özel istek onaylandı: <başlık>" && git push origin main`.
   (Push videoyu hemen üretime sokar.) İstek belgesini `update`: `{"durum": "onaylandi", "senaryo": "<dosya adı>"}`.
   Red: `taslaklar/reddedilen/`e taşı, push et, istek belgesini `{"durum": "reddedildi", "mesaj": "<neden>"}` yap.
4. Panel postasına kısa mail (anahtarın `editor`): onay/red ve nedeni.
