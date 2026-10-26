# 📅 Haftalık plan talimatı – Viteskop (yazar, her pazar)

Sayfa sahibi kapak görsellerini kendisi ChatGPT'de hazırlıyor. Bunun için **gelecek haftanın planını** önceden ister.
Planı **Viteskop Paneli**'nin veritabanındaki `plan` koleksiyonuna yazarsın (ArtifactData; yüklü değilse ToolSearch:
`select:ArtifactData`), url: https://claude.ai/artifact/Bbptq64xnkCdhrqCEiowhr

## 1. Hazırlık
`git pull origin main`. `ekip/yazar.md`, `SENARYO.md`, son `senaryolar/` ve varsa son raporları oku.
Paneldeki `plan` koleksiyonunu oku (`list`): önceki haftalarda planlanan konuları tekrar etme.

## 2. Gelecek pazartesiden pazara 14 video planla (günde 2: 12:30 ve 20:00)
Seri dağılımı (haftalık): Kafa Kafaya 2, Bakım Saati 4, Arıza Alarmı 4, Parça Rehberi 4. Aynı gün iki aynı seri olmasın.
Mevsimi ve gündemi düşün (kış lastiği, antifriz, uzun yol, bayram, yeni çıkan modeller…).
Kafa Kafaya için Türkiye'de satılan aynı sınıf iki model seç; versiyonları (model yılı, motor, şanzıman, donanım) şimdiden belirle.

## 3. Her video için bir belge yaz
`action: "set"`, `collection: "plan"`, `doc_id`: `YYYYAAGG-N` (N: 1 = 12:30, 2 = 20:00). Var olan belgeye yazacaksan
önce `get` ile oku ve `if_version` ver; sayfa sahibinin yüklediği görsel alanlarına (`gorsel_*`) **dokunma** (`update` kullan).
Alanlar:
- `tarih` ("2026-11-02"), `saat` ("12:30"), `seri` (kafa/bakim/ariza/parca), `durum`: "planlandi"
- `konu` (tek cümle), `baslik` (videonun başlığı), `kapak`: 2–3 kısa büyük harf satır (["MOTOR YAĞI", "NE ZAMAN", "DEĞİŞİR?"])
- `gorsel_istemi`: sayfa sahibinin ChatGPT'ye yapıştıracağı **Türkçe** istem. Şunları mutlaka içersin:
  - "Dikey 9:16 Instagram Reels kapağı, 1080x1920."
  - Kapakta yazacak Türkçe yazılar, tırnak içinde, büyük harf, Türkçe karakterler doğru ("MOTOR YAĞI NE ZAMAN DEĞİŞİR?").
  - "Bütün yazılar ve önemli öğeler görselin ortadaki 3/4'lük alanında kalsın (üst ve alttaki %12'lik şeritler boş kalsın; profil ızgarası orayı keser)."
  - Sahne: dramatik, sinematik, yüksek kontrast, koyu tonlar, turuncu/kırmızı vurgu ışıkları; konuya uygun gerçekçi görüntü.
  - Kafa Kafaya: iki aracın adı, ortada "VS"; **tarafsız**: iki taraf eşit büyüklükte, kazanan ima eden yazı ya da işaret yok.
    Soru yazısı tarafsız olsun ("HANGİSİNİ SEÇERDİN?", "HİBRİT Mİ TURBO MU?").
  - "Yanlış yazı, uydurma rakam ya da sahte logo olmasın." (Rakam yazdırma; rakamlar videoda.)
  - Tık tuzağı yok ("ŞOK", "KİMSE BİLMİYOR" gibi).

## 4. Bitir
Panel postasına `tur: "rapor"`, konu "Gelecek haftanın planı hazır" diye kısa mail at (`ekip/iletisim.md`, anahtarın `yazar`):
14 başlığı gün gün listele ve "Görselleri Haftalık Plan bölümünden yükleyebilirsin" yaz.

## Günlük senaryo yazarken
Her sabah o günün plan belgelerini (`tarih` = bugün) oku ve senaryoyu plana göre yaz: dosya adı `YYYYAAGG-N-kisa-ad.json`
(plan kimliğiyle başlasın), `kapak` alanını plandakiyle aynı yap. Sonra plan belgesini `update` ile
`{"durum": "senaryo", "senaryo": "<dosya adı>"}` yap. Planda bir sorun görürsen (bilgi bulunamadı vb.) değiştir ve postada söyle.
