/* Posta + Toplantı Odası: hem clufive Paneli'nde hem Kampüs'te kullanılır.
   Veriler sayfanın kendi veritabanında:
     posta/<id>     {kimden, konu, metin, tur: rapor|soru|bilgi|brifing, zaman, okundu, yanit, yanit_zaman}
     toplanti/<id>  {kimden, kime: ["hepsi"] | [anahtarlar], metin, zaman}
     ayarlar/ekip   {kisiler: {anahtar: {ad, renk, rol, tetik}}}  (tetik: ajanın toplantı çağrısı rutini; "çağır" bunu çalıştırır)
   Ajanlar bu belgeleri ArtifactData aracıyla okur/yazar (bkz. ekip/iletisim.md). */
(function () {
  "use strict";
  var AYAR = window.ILETISIM_AYAR; if (!AYAR) return;
  var SUNUCU = "Claude Code Remote";
  var kisiler = AYAR.kisiler;
  var postaEl = document.getElementById("posta-listesi"), toplantiEl = document.getElementById("toplanti-akis");
  var rozetler = document.querySelectorAll("[data-posta-rozet]");
  var db = null, mcp = null, sample = null;

  function el(t, c, m) { var e = document.createElement(t); if (c) e.className = c; if (m != null) e.textContent = m; return e; }
  function once(iso) {
    var f = (Date.now() - new Date(iso).getTime()) / 60000;
    if (isNaN(f)) return "";
    if (f < 1) return "az önce"; if (f < 60) return Math.round(f) + " dk önce"; if (f < 1440) return Math.round(f / 60) + " sa önce";
    return new Date(iso).toLocaleDateString("tr-TR", {day: "numeric", month: "short"}) + " " + new Date(iso).toLocaleTimeString("tr-TR", {hour: "2-digit", minute: "2-digit", timeZone: "Europe/Istanbul"});
  }
  function kisi(k) { return kisiler[k] || {ad: k === "sahip" ? "Sen" : k, renk: k === "sahip" ? "#18233c" : "#8a93a8"}; }
  function avatar(k) { var a = el("span", "kisi-av"); a.style.background = kisi(k).renk; a.textContent = (kisi(k).ad || "?").slice(0, 1); a.title = kisi(k).ad; return a; }
  function durum(kap, metin, hata) { var d = kap.querySelector(".ilt-durum"); if (d) { d.textContent = metin || ""; d.dataset.hata = hata ? "1" : "0"; } }

  // ---------------------------------------------------------------- Posta
  var acik = {};
  function postaCiz(belgeler) {
    if (!postaEl) return;
    var okunmamis = belgeler.filter(function (b) { return !b.v.okundu; }).length;
    rozetler.forEach(function (r) { r.textContent = okunmamis ? String(okunmamis) : ""; r.hidden = !okunmamis; });
    postaEl.textContent = "";
    if (!belgeler.length) { postaEl.appendChild(el("p", "ilt-bos", "Henüz posta yok. Ajanlar işlerini bitirince raporlarını buraya gönderecek.")); return; }
    belgeler.forEach(function (b) {
      var v = b.v, li = el("article", "mail"); li.dataset.okundu = v.okundu ? "1" : "0"; li.dataset.tur = v.tur || "bilgi";
      var bas = el("button", "mail-bas"); bas.type = "button"; bas.setAttribute("aria-expanded", acik[b.id] ? "true" : "false");
      bas.appendChild(avatar(v.kimden));
      var yazi = el("span", "mail-yazi");
      var ust = el("span", "mail-ust"); ust.appendChild(el("b", null, kisi(v.kimden).ad)); ust.appendChild(el("span", "mail-zaman", once(v.zaman)));
      yazi.appendChild(ust); yazi.appendChild(el("span", "mail-konu", v.konu || "(konu yok)"));
      bas.appendChild(yazi);
      bas.appendChild(el("span", "mail-tur", {rapor: "Rapor", soru: "Soru", bilgi: "Bilgi", brifing: "Brifing"}[v.tur] || "Bilgi"));
      li.appendChild(bas);
      var govde = el("div", "mail-govde"); govde.hidden = !acik[b.id];
      govde.appendChild(el("div", "mail-metin", v.metin || ""));
      if (v.yanit) {
        var y = el("div", "mail-yanit"); y.appendChild(el("b", null, "Yanıtın · " + once(v.yanit_zaman))); y.appendChild(el("div", null, v.yanit)); govde.appendChild(y);
      } else if (db) {
        var ta = el("textarea"); ta.rows = 2; ta.placeholder = kisi(v.kimden).ad + " kişisine yanıt yaz…"; ta.id = "yanit-" + b.id;
        var btn = el("button", "ilt-btn", "Yanıtla"); btn.type = "button";
        var dd = el("span", "ilt-durum");
        btn.addEventListener("click", function () {
          var m = ta.value.trim(); if (!m) return;
          btn.disabled = true; durum(govde, "Gönderiliyor…");
          db.collection("posta").doc(b.id).update({yanit: m, yanit_zaman: new Date().toISOString(), okundu: true})
            .then(function () { durum(govde, "Gönderildi. " + kisi(v.kimden).ad + " bir sonraki çalışmasında okuyacak."); })
            .catch(function (e) { btn.disabled = false; durum(govde, "Gönderilemedi: " + (e && e.message || e), true); });
        });
        var satir = el("div", "ilt-satir"); satir.appendChild(btn); satir.appendChild(dd);
        govde.appendChild(ta); govde.appendChild(satir);
      }
      li.appendChild(govde);
      bas.addEventListener("click", function () {
        acik[b.id] = !acik[b.id]; govde.hidden = !acik[b.id]; bas.setAttribute("aria-expanded", acik[b.id] ? "true" : "false");
        if (acik[b.id] && !v.okundu && db) db.collection("posta").doc(b.id).update({okundu: true}).catch(function () {});
      });
      postaEl.appendChild(li);
    });
  }

  // ---------------------------------------------------------------- Toplantı Odası
  var secili = {hepsi: true};
  var mesajlar = [];
  function katilimcilarCiz() {
    var k = document.getElementById("toplanti-katilimcilar"); if (!k) return;
    k.textContent = "";
    Object.keys(kisiler).forEach(function (a) {
      var c = el("span", "katilimci"); c.appendChild(avatar(a)); c.appendChild(el("span", null, kisiler[a].ad));
      if (kisiler[a].rol) c.appendChild(el("small", null, kisiler[a].rol));
      k.appendChild(c);
    });
    var alici = document.getElementById("toplanti-alici"); if (!alici) return;
    alici.textContent = "";
    [["hepsi", "Herkes"]].concat(Object.keys(kisiler).map(function (a) { return [a, kisiler[a].ad]; })).forEach(function (s) {
      var b = el("button", "alici", s[1]); b.type = "button"; b.setAttribute("aria-pressed", secili[s[0]] ? "true" : "false");
      b.addEventListener("click", function () {
        if (s[0] === "hepsi") secili = {hepsi: true}; else { delete secili.hepsi; secili[s[0]] = !secili[s[0]]; if (!Object.keys(secili).some(function (x) { return secili[x]; })) secili = {hepsi: true}; }
        katilimcilarCiz();
      });
      alici.appendChild(b);
    });
  }
  function toplantiCiz() {
    if (!toplantiEl) return;
    var asagida = toplantiEl.scrollHeight - toplantiEl.scrollTop - toplantiEl.clientHeight < 60;
    toplantiEl.textContent = "";
    if (!mesajlar.length) toplantiEl.appendChild(el("p", "ilt-bos", AYAR.bosToplanti || "Toplantı odası boş. İlk mesajı sen yaz."));
    mesajlar.forEach(function (v) {
      var m = el("div", "msj"); m.dataset.ben = v.kimden === "sahip" ? "1" : "0";
      m.appendChild(avatar(v.kimden));
      var g = el("div", "msj-govde");
      var ust = el("div", "msj-ust"); ust.appendChild(el("b", null, kisi(v.kimden).ad));
      var kime = (v.kime || ["hepsi"]).map(function (x) { return x === "hepsi" ? "herkes" : kisi(x).ad; }).join(", ");
      ust.appendChild(el("span", null, "→ " + kime + " · " + once(v.zaman)));
      g.appendChild(ust); g.appendChild(el("div", "msj-metin", v.metin));
      m.appendChild(g); toplantiEl.appendChild(m);
    });
    if (asagida) toplantiEl.scrollTop = toplantiEl.scrollHeight;
  }
  function seciliListe() { return secili.hepsi ? ["hepsi"] : Object.keys(secili).filter(function (x) { return secili[x]; }); }
  function gonder(metin) {
    return db.collection("toplanti").add({kimden: "sahip", kime: seciliListe(), metin: metin, zaman: new Date().toISOString()});
  }
  function cagir(metin) {
    // "Herkes" seçiliyse çağrı rutini olan herkes gelir (önce yönetici)
    var hedefler = secili.hepsi ? [AYAR.yonetici].concat(Object.keys(kisiler).filter(function (a) { return a !== AYAR.yonetici && kisiler[a].tetik; })) : seciliListe();
    // Her ajanın "toplantı çağrısı" rutini var (sabit talimatlı, saati yok); düğme onu hemen çalıştırır.
    var istekler = hedefler.filter(function (a) { return kisiler[a] && kisiler[a].tetik; }).map(function (a) {
      return mcp.callTool(SUNUCU, "fire_trigger", {trigger_id: kisiler[a].tetik});
    });
    if (!istekler.length) return Promise.reject({message: "Bu kişinin toplantı çağrısı rutini yok."});
    return Promise.all(istekler).then(function () { return hedefler.map(function (a) { return kisi(a).ad; }).join(", "); });
  }
  function beyneSor(metin) {
    var son = mesajlar.slice(-15).map(function (v) { return kisi(v.kimden).ad + ": " + v.metin; }).join("\n");
    var baglam = AYAR.baglam ? AYAR.baglam() : "";
    var girdi = "Sen " + AYAR.beyinRol + " Sayfa sahibiyle Türkçe, sade, kısa (en fazla 6 cümle) ve somut konuş. " +
      "Kararı sahibine bırak; öneri ver, gerekirse hangi ajanın neyi yapması gerektiğini söyle. Uydurma rakam verme; bilmiyorsan söyle.\n\n" +
      "GÜNCEL DURUM:\n" + baglam + "\n\nTOPLANTIDAKİ SON MESAJLAR:\n" + son + "\n\nSAHİBİN YENİ MESAJI:\n" + metin;
    return sample(girdi, {modelTier: "default", cache: false}).then(function (r) {
      return db.collection("toplanti").add({kimden: "beyin", kime: ["sahip"], metin: (r.text || "").trim(), zaman: new Date().toISOString()});
    });
  }
  function formKur() {
    var form = document.getElementById("toplanti-form"); if (!form) return;
    var ta = document.getElementById("toplanti-metin"), kap = form;
    form.addEventListener("submit", function (e) { e.preventDefault(); });
    form.querySelectorAll("[data-islem]").forEach(function (b) {
      b.addEventListener("click", function () {
        var metin = ta.value.trim(); if (!metin || !db) return;
        var islem = b.dataset.islem;
        form.querySelectorAll("[data-islem]").forEach(function (x) { x.disabled = true; });
        durum(kap, islem === "beyin" ? "Beyin düşünüyor…" : "Gönderiliyor…");
        gonder(metin).then(function () {
          ta.value = "";
          if (islem === "cagir") return cagir(metin).then(function (adlar) { durum(kap, adlar + " çağrıldı; her biri birkaç dakika içinde burada fikrini yazacak."); },
            function (e) { durum(kap, "Mesajın kaydedildi ama ajanlar şu an uyandırılamadı (" + (e && (e.message || e.code) || e) + "). Oda müdürü en geç bir sonraki çalışmasında (08:10 · 11:10 · 14:10 · 17:10 · 21:10) cevap verir.", true); });
          if (islem === "beyin") {
            if (!sample) { durum(kap, "Mesaj kaydedildi. Bu görünümde Beyin'e anında sorulamıyor; sayfayı claude.ai'de aç.", true); return; }
            return beyneSor(metin).then(function () { durum(kap, ""); }, function (e) { durum(kap, "Mesaj kaydedildi ama Beyin cevap veremedi: " + (e && (e.message || e.code) || e), true); });
          }
          durum(kap, "Gönderildi. Ajanlar bir sonraki çalışmalarında okuyacak.");
        }).catch(function (e) { durum(kap, "Gönderilemedi: " + (e && e.message || e), true); })
          .then(function () { form.querySelectorAll("[data-islem]").forEach(function (x) { x.disabled = false; }); });
      });
    });
  }

  // ---------------------------------------------------------------- bağlantı
  katilimcilarCiz(); formKur(); postaCiz([]); toplantiCiz();
  var cl = window.claude; if (!cl || !cl.use) return;
  cl.use("db").then(function (d) {
    if (!d) return; db = d;
    d.doc("ayarlar/ekip").onSnapshot(function (s) {
      if (s.exists && s.data().kisiler) { kisiler = Object.assign({}, AYAR.kisiler, s.data().kisiler); katilimcilarCiz(); toplantiCiz(); }
    }, function () {});
    d.collection("posta").orderBy("zaman", "desc").limit(60).onSnapshot(function (qs) {
      postaCiz(qs.docs.filter(function (x) { return x.exists; }).map(function (x) { return {id: x.id, v: x.data()}; }));
    }, function () {});
    d.collection("toplanti").orderBy("zaman", "desc").limit(80).onSnapshot(function (qs) {
      mesajlar = qs.docs.filter(function (x) { return x.exists; }).map(function (x) { return x.data(); }).reverse(); toplantiCiz();
    }, function () {});
  });
  cl.use("mcp").then(function (m) { mcp = m; });
  cl.use("sample").then(function (s) { sample = s; });
})();
