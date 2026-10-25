# 🖼️ Kapak görseli aktarma – Viteskop (oda müdürü)

Sayfa sahibi kapak görsellerini **Viteskop Paneli → Haftalık Plan → Görsel yükle** ile yükler. Sen bunları depoya taşırsın;
kapak üretici (`kapak.py`) `kapaklar/` klasöründekileri kullanır. Panel: https://claude.ai/artifact/Bbptq64xnkCdhrqCEiowhr

1. `git pull origin main`.
2. Paneldeki `plan` koleksiyonunda `gorsel_id` dolu ve `gorsel_islendi` false olan belgeleri bul (`query`).
   Her biri için görseli indir: Artifact aracı `action: "read"`, `url`: panel adresi, `path`: `gorsel_id` (dosyayı yerel bir
   klasöre kaydeder, sonuç yolunu söyler). Görseli `kapaklar/<doc_id>.jpg` olarak kaydet (`gorsel_turu` "arka" ise
   `kapaklar/<doc_id>-arka.jpg`); PNG/WEBP ise `python -c "from PIL import Image; Image.open('GIRDI').convert('RGB').save('CIKTI', quality=92)"` ile JPG'ye çevir.
   Sonra `git add kapaklar/ && git commit -m "Kapak görseli: <doc_id>" && git push origin main` (gerekirse `git pull --rebase`),
   ve belgeyi `update` ile `{"gorsel_islendi": true}` yap. **Depoda yalnızca `kapaklar/` klasörüne yazma iznin var.**
3. Bitince tek cümle: hangi plan belgelerinin görseli aktarıldı (yoksa "aktarılacak görsel yok").

Kurallar: Depoda yalnızca `kapaklar/` klasörüne yaz ve commit/push et. Veritabanında yalnızca `plan` belgelerinin `gorsel_islendi` alanını değiştir.
