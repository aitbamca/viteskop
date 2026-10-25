# Viteskop senaryo biçimi

Her video `senaryolar/YYYYAAGG-N-kisa-ad.json` dosyasıdır. `senaryolar/`a giren dosya otomatik
videoya çevrilir (GitHub Actions, Gemini sesi Iapetus). Deneme: `python video.py senaryolar/X.json /tmp/x.mp4`
(bu ortamda Gemini anahtarı yoksa `SES_SAGLAYICI=espeak` ile robotik sesle çalışır, görüntü aynıdır).

## Üst alanlar

| Alan | Açıklama |
|---|---|
| `baslik` / `baslik_en` | Kısa soru ya da merak cümlesi (en fazla ~32 karakter) |
| `seri` | `kafa` (Kafa Kafaya), `bakim` (Bakım Saati), `ariza` (Arıza Alarmı), `parca` (Parça Rehberi). Rengi, temayı ve kapanış sorusunu belirler |
| `tema` | İsteğe bağlı: `garaj`, `showroom`, `otoyol`, `gece_sehir`, `gosterge` (yoksa serinin teması) |
| `soru` | İsteğe bağlı kapanış sorusu (yoksa serinin sorusu) |
| `aciklama` / `aciklama_en` | Instagram açıklaması: yorum ve kaydetmeye davet |
| `etiketler` | 8–12 hashtag, ilki `#viteskop` |
| `kaynaklar` | Doğrulanan kaynaklar (üretici, resmi kurum, kullanım kitapçığı). Editör kontrol eder |

## Sahneler

Her sahnede `tip`, `metin` (Türkçe seslendirme) ve `metin_en` (İngilizce altyazı, **cümle sayısı Türkçeyle aynı**) olur.
İlk sahne `giris`, son sahne `kapanis`. Toplam 100–130 kelime, 5–7 sahne (45–60 sn).

| Tip | Alanlar | Ne gösterir |
|---|---|---|
| `giris` | `alt` (isteğe bağlı küçük açıklama; kıyasta versiyonlar) | Seri etiketi, sola yaslı büyük başlık, arabanın teknik çizimi |
| `bilgi` | `yazi` | Büyük yazı kartı |
| `kiyas` | `sol`, `sag` (`ad`, `tip`: sedan/suv/hatchback/pickup, `surum`, `donanim`), `satirlar` (en fazla 5: `ad`, `sol`, `sag`, `anahtar`) | İki arabanın teknik çizimi ve rakamlara göre uzayan karşılaştırma çubukları (kazanan işaretlenmez) (değerlerde sayı olsun: "441 L") |
| `araba` | `araba` (tip, renk), `yazi`, `etiketler` (`yazi`, `x`, `y` 0–1 arabanın üstündeki yer, `anahtar`) | Araba gelir, parçaları etiketlenir |
| `ikaz` | `ikon` (motor, yag, aku, sicaklik, fren, lastik_basinci, abs, hava_yastigi), `renk` (sari/kirmizi/yesil/mavi), `yazi`, `yanip` (true/false; kırmızıda varsayılan true) | Gösterge paneli ve ikaz lambası |
| `liste` | `maddeler` (en fazla 5, kısa), `anahtarlar`, isteğe bağlı `baslik` | Numaralı maddeler (01, 02…) |
| `parca` | `parca` (lastik, fren_diski, aku, yag_bidonu, buji, anahtar, filtre, silecek), `yazi`, `notlar` (en fazla 3), `anahtarlar` | Büyük parça çizimi ve notlar |
| `gosterge` | `deger` (0–1), `yazi`, `alt` | İğnesi yükselen gösterge |
| `uyari` | `yazi` | Güvenlik uyarısı (üçgen) |
| `kapanis` | `soru` (isteğe bağlı) | Soru, "Yorumlara yaz!", "Kaydet, lazım olur" |

`anahtar`/`anahtarlar`: öğenin, metindeki bu kelime okunduğu anda belirmesi için (kelimenin başı yeter: "fren").

Hazır sahneler yetmezse senaryonun yanına aynı adla `.py` yazılabilir (`SAHNELER = {"tip": fonksiyon}`,
`ARKA_PLANLAR`, `hazirla()`); fonksiyon `sahne(z, t, s)` biçimindedir (bkz. `video.py`).

## Görsel dil
Ciddi, teknik bir oto kanalı: koyu stüdyo zemin, sola yaslı tipografi, çizgisel teknik çizimler, veri çubukları.
Çizgi film havası verecek şeylerden kaçın (abartılı ünlemler, "hadi bakalım" gibi sevimli ifadeler, emoji yağmuru).

## Kurallar
- **Güvenlik:** Fren, direksiyon, hava yastığı, yakıt ve yüksek voltaj işlerinde "kendin yap" deme, ustaya yönlendir.
- **Doğruluk:** Her rakamı kaynağıyla yaz. Kesin aralıklar için "aracının kitapçığına bak" de.
- **Kafa Kafaya'da tarafsızlık (sayfa sahibinin kuralı):** Taraf tutmayız, kazanan seçmeyiz, sonunda karar vermeyiz.
  Sadece doğrulanmış rakamları ve her arabanın öne çıkan özelliğini aynı tonda söyleriz; kararı izleyiciye sorarız.
  "Daha iyi", "fark atıyor", "kazanan", "tercih edilmeli" gibi ifadeler kullanılmaz. `kiyas` satırlarına `kazanan` yazılmaz.
- **Hangi versiyon:** Kıyasta her araba için model yılı, motor (hacim ve güç), şanzıman ve donanım paketi açıkça yazılır:
  `kiyas` sahnesinde `surum` ("1.0 TSI 116 PS · DSG") ve `donanim` ("Life · 2026 model"), `giris`te `alt`
  ("… Flame vs … Life · 2026 model") ve girişin metninde söylenir. Bütün rakamlar bu versiyona ait olmalıdır.
- **Fiyatlar:** Kıyasta fiyat varsa ay ve yılı yaz ("Ekim 2026 liste fiyatı").
- **Marka:** Arabalar marka taklidi değil, sade silüettir. Marka adı yalnız kıyasta, bilgi amaçlı geçer.
