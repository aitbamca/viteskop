/* ⚡ Özel istek: sayfa sahibi program dışı bir konu ister; yazarın özel istek rutini hemen çağrılır.
   Ayarlar: window.ISTEK_AYAR = {yazarTetik: "trig_...", ornek: "..."}
   Veritabanı: istek/<id> {konu, not, zaman, durum: bekliyor|taslak|onaylandi|reddedildi, taslak, senaryo, mesaj} */
(function () {
  var AYAR = window.ISTEK_AYAR || {};
  var kok = document.getElementById("istek");
  if (!kok) return;
  var liste = kok.querySelector("[data-istek-liste]");
  var form = kok.querySelector("form");
  var konu = form.querySelector("[name=konu]"), not = form.querySelector("[name=not]");
  var durumYazi = form.querySelector("[data-istek-durum]"), dugme = form.querySelector("button");
  var DURUM = {bekliyor: ["Yazar çağrıldı", "bekliyor"], taslak: ["Taslak yazıldı, editörde", "taslak"],
               onaylandi: ["Onaylandı: video üretimde / sırada ilk", "onay"], reddedildi: ["Reddedildi", "red"]};
  var db = null, mcp = null;
  function el(t, s, m) { var e = document.createElement(t); if (s) e.className = s; if (m != null) e.textContent = m; return e; }
  function once(iso) {
    var d = new Date(iso); if (isNaN(d)) return "";
    return d.toLocaleString("tr-TR", {timeZone: "Europe/Istanbul", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit"});
  }
  function ciz(kayitlar) {
    liste.textContent = "";
    if (!kayitlar.length) { liste.appendChild(el("p", "ilt-bos", "Henüz özel istek yok.")); return; }
    kayitlar.forEach(function (v) {
      var kart = el("div", "istek-kart");
      var ust = el("div", "istek-ust");
      ust.appendChild(el("b", null, v.konu || ""));
      var d = DURUM[v.durum] || [v.durum || "", "bekliyor"];
      var rozet = el("span", "istek-durum", d[0]); rozet.dataset.d = d[1]; ust.appendChild(rozet);
      kart.appendChild(ust);
      var alt = once(v.zaman) + (v.senaryo ? " · " + v.senaryo : v.taslak ? " · " + v.taslak : "") + (v.mesaj ? " · " + v.mesaj : "");
      kart.appendChild(el("small", null, alt));
      liste.appendChild(kart);
    });
  }
  function yaz(m, hata) { durumYazi.textContent = m; durumYazi.dataset.hata = hata ? "1" : "0"; }
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var k = konu.value.trim(); if (!k || !db) return;
    dugme.disabled = true; yaz("Gönderiliyor…");
    db.collection("istek").add({konu: k, not: not.value.trim(), zaman: new Date().toISOString(), durum: "bekliyor"}).then(function () {
      konu.value = ""; not.value = "";
      if (!mcp || !AYAR.yazarTetik) { yaz("İstek kaydedildi. Editör günde iki kez özel istekleri kontrol eder; yazar bir sonraki çalışmasında yazar."); return; }
      return mcp.callTool("Claude Code Remote", "fire_trigger", {trigger_id: AYAR.yazarTetik}).then(function () {
        yaz("Yazar çağrıldı. Taslak birkaç dakikada yazılır, editör onaylayınca video kota müsaitse hemen üretilir ve ilk boş paylaşım saatinde yayınlanır.");
      }, function (h) { yaz("İstek kaydedildi ama yazar şu an çağrılamadı (" + ((h && (h.code || h.message)) || "hata") + "). Bir sonraki çalışmada yazılır.", true); });
    }, function (h) { yaz("Kaydedilemedi: " + ((h && (h.code || h.message)) || "hata"), true); })
      .then(function () { dugme.disabled = false; });
  });
  if (AYAR.ornek) konu.placeholder = AYAR.ornek;
  ciz([]);
  var cl = window.claude; if (!cl || !cl.use) { yaz("İstek göndermek için sayfayı Claude'da aç.", true); dugme.disabled = true; return; }
  cl.use("mcp").then(function (m) { mcp = m; }, function () {});
  cl.use("db").then(function (d) {
    if (!d) { yaz("İstek göndermek için sayfayı Claude'da aç.", true); dugme.disabled = true; return; }
    db = d;
    d.collection("istek").orderBy("zaman", "desc").limit(8).onSnapshot(function (qs) {
      ciz(qs.docs.filter(function (x) { return x.exists; }).map(function (x) { return x.data(); }));
    }, function () {});
  });
})();
