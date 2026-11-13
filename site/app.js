/* Hidden Water Index — client. Data: data.json (Overture Maps + Wikidata).
   Reviews: posted to REVIEW_ENDPOINT if set, otherwise kept in this browser only. */

const REVIEW_ENDPOINT = ""; // set to a URL (POST/GET JSON) once a backend exists

const SCORED = [
  {d:0,n:"Seitan Limania",c:"beach",D:8,C:8.5,W:10,hex:"#729E96",hue:169,sat:.28,ok:1,
   t:"A cleft in the limestone at the end of a dirt track on Akrotiri. Deep off the shingle, with rock high enough to jump from."},
  {d:0,n:"Katholiko Bay",c:"beach",D:8.5,C:7.5,W:10,ok:1,
   t:"Two kilometres down the Avlaki ravine past an 11th-century monastery cut into the cliff. No beach — entry is off stone."},
  {d:0,n:"Agiofarango",c:"beach",D:8,C:8,W:10,
   t:"A 2.5 km gorge from Odigitria monastery to a cove with no road. Boats reach it in summer; from October the walk is the only way in."},
  {d:0,n:"Marmara",c:"beach",D:8,C:8,W:10,
   t:"At the foot of the Aradena gorge, under a 138-metre iron bridge and ladders bolted into rock. Twenty minutes on foot from Lykos."},
  {d:0,n:"Lissos",c:"beach",D:8,C:8,W:10,
   t:"An ancient healing sanctuary above a pebble bay, reached on foot over a ridge from Sougia or by boat in season. Unverified."},
  {d:0,n:"Glyka Nera",c:"beach",D:7.5,C:8,W:10,ok:1,
   t:"Thirty minutes along the coast path from Chora Sfakion. Freshwater springs rise through the shingle and cool the whole bay."},
  {d:0,n:"Preveli",c:"beach",D:7,C:8,W:10,hex:"#508FA9",hue:197.5,sat:.53,ok:1,
   t:"Where the Kourtaliotiko river meets the Libyan Sea under a palm grove. The grove burned in July 2026 and is early in a recovery measured in years."},
  {d:0,n:"Balos",c:"beach",D:6,C:9.5,W:10,hex:"#49929E",hue:188,sat:.54,
   t:"A sandbar between a lagoon and the open sea. The highest colour measured in Crete, and cut: a car park above, umbrella rows below."},
  {d:0,n:"Elafonissi",c:"beach",D:6,C:9,W:10,ok:1,
   t:"Pink shell sand on the south-west tip, shallow enough to stand a hundred metres out. Famous, and cut on Discovery once walked."},
  {d:0,n:"Kourtaliotiko",c:"todo",D:8,C:7,W:4,ok:1,
   t:"A gorge above Preveli with pools under a waterfall. Cut on Water: Cretan gorge freshwater measures about 14°C."}
];
const ACC = [
  ["Seitan Limania","Colour","8","8.5","+0.5"],["Elafonissi","Colour","9","9","0"],
  ["Glyka Nera","Colour","8","8","0"],["Katholiko","Colour, no photograph existed","7.5","7.5","0"],
  ["Elafonissi","Discovery","8","6","−2.0"],["Preveli","Discovery","5","7","+2.0"],
  ["Glyka Nera","Discovery","8","7.5","−0.5"],["Katholiko","Discovery","6.5","8.5","+2.0"]
];
const AUTO = [
  ["Seitan Limania","8","8.0","0"],["Katholiko","8.5","8.0","−0.5"],["Glyka Nera","7.5","7.5","0"],
  ["Preveli","7","7.0","0"],["Elafonissi","6","6.0","0"],["Balos","6","8.0","+2.0"]
];
const DESTS = [[0,"Crete"],[1,"Zanzibar"],[2,"Sulawesi"]];
const CATS = [["all","Everything"],["beach","Beaches"],["adventure","Adventures"],["food","Restaurants"],
  ["club","Bars & clubs"],["todo","Things to do"],["hotel","Hotels"],["indoor","Indoor"],["shop","Shops & markets"]];
const CATLAB = {beach:"Beach",food:"Restaurant",club:"Bar or club",todo:"Thing to do",
  indoor:"Indoor",hotel:"Hotel",shop:"Shop",guide:"Guide",adventure:"Adventure"};
const MIDLAT = [35.24,-5.80,-2.00];

let DATA = [], dest = 0, cat = "all", q = "", shown = 48, gshown = 36, gdest = 0, REV = {};
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"]/g, m => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[m]));
const fmt = n => n.toLocaleString("en-GB");
const keyOf = (name, d) => (d + "|" + name).toLowerCase().replace(/[^a-z0-9|]+/g, "-").slice(0, 120);

/* ---------- reviews ---------- */
function loadReviews() {
  if (REVIEW_ENDPOINT) {
    return fetch(REVIEW_ENDPOINT).then(r => r.json()).then(list => { index(list); }).catch(() => {});
  }
  try { index(JSON.parse(localStorage.getItem("hwi-reviews") || "[]")); } catch (e) {}
  return Promise.resolve();
}
function index(list) {
  REV = {};
  (list || []).forEach(v => { const k = keyOf(v.place, v.dest); (REV[k] = REV[k] || []).push(v); });
  const n = Object.values(REV).reduce((s, a) => s + a.length, 0);
  if ($("s-rev")) $("s-rev").textContent = fmt(n);
}
async function saveReview(rec) {
  if (REVIEW_ENDPOINT) {
    const r = await fetch(REVIEW_ENDPOINT, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(rec)});
    if (!r.ok) throw new Error("server " + r.status);
  } else {
    let all = [];
    try { all = JSON.parse(localStorage.getItem("hwi-reviews") || "[]"); } catch (e) {}
    all.push(rec);
    localStorage.setItem("hwi-reviews", JSON.stringify(all));
  }
  const k = keyOf(rec.place, rec.dest);
  (REV[k] = REV[k] || []).push(rec);
  const n = Object.values(REV).reduce((s, a) => s + a.length, 0);
  $("s-rev").textContent = fmt(n);
}
function revBlock(name, d, autoD) {
  const k = keyOf(name, d), list = REV[k] || [];
  const avg = f => list.length ? list.reduce((s, x) => s + (+x[f] || 0), 0) / list.length : null;
  const w = document.createElement("div"); w.className = "rev";
  const head = document.createElement("div"); head.className = "revline";
  const mean = list.length ? ["D","C","W"].map(f => f + " " + avg(f).toFixed(1).replace(/\.0$/, "")).join("  ") : "";
  head.innerHTML = "<span>" + (list.length
    ? list.length + (list.length === 1 ? " review · " : " reviews · ") + mean
    : "No reviews yet") + "</span>";
  const btn = document.createElement("button");
  btn.className = "revbtn"; btn.type = "button"; btn.textContent = "Review";
  head.appendChild(btn); w.appendChild(head);
  if (list.length) {
    const ul = document.createElement("div"); ul.className = "revlist";
    list.slice(-3).forEach(x => {
      const li = document.createElement("div"); li.className = "revitem";
      li.innerHTML = "<b>D " + esc(x.D) + " · C " + esc(x.C) + " · W " + esc(x.W) + "</b>";
      if (x.note) { const p = document.createElement("div"); p.textContent = x.note; li.appendChild(p); }
      ul.appendChild(li);
    });
    w.appendChild(ul);
  }
  btn.onclick = () => {
    if (w.querySelector("form")) return;
    btn.hidden = true;
    const f = document.createElement("form"); f.className = "revform";
    f.innerHTML = '<div class="revrow">'
      + '<label>Discovery<input type="number" min="1" max="10" step="0.5" value="' + autoD + '" required></label>'
      + '<label>Colour<input type="number" min="1" max="10" step="0.5" required></label>'
      + '<label>Water<input type="number" min="1" max="10" step="0.5" required></label></div>'
      + '<textarea placeholder="What was it actually like? Walk time, access, whether anyone was there."></textarea>'
      + '<div class="act"><button type="submit">Post review</button><span class="msg"></span></div>';
    const msg = f.querySelector(".msg");
    if (!REVIEW_ENDPOINT) msg.textContent = "Saved in this browser only — no server yet.";
    f.onsubmit = async ev => {
      ev.preventDefault();
      const [D, C, W] = [...f.querySelectorAll("input")].map(i => parseFloat(i.value));
      const note = f.querySelector("textarea").value.trim().slice(0, 600);
      msg.textContent = "Saving…";
      try { await saveReview({place:name, dest:d, D, C, W, note, at:new Date().toISOString()}); render(); }
      catch (e) { msg.textContent = "Could not save (" + e.message + ")."; }
    };
    w.insertBefore(f, w.children[1] || null);
  };
  return w;
}

/* ---------- cards ---------- */
function chips(host, items, cur, on, counts) {
  host.innerHTML = "";
  items.forEach(([v, l]) => {
    const b = document.createElement("button");
    b.className = "chip"; b.type = "button";
    b.innerHTML = esc(l) + (counts && counts[v] != null ? '<span class="n">' + fmt(counts[v]) + "</span>" : "");
    b.setAttribute("aria-pressed", String(v === cur));
    b.onclick = () => on(v);
    host.appendChild(b);
  });
}
const tot = p => p.D + p.C + p.W;
const weak = p => Math.min(p.D, p.C, p.W) < 7;
function photoEl(url, name) {
  if (!url) return '<div class="nophoto"><span>No photograph yet</span></div>';
  const src = url.replace("/wiki/Special:FilePath/", "/wiki/Special:FilePath/");
  return '<img class="photo" loading="lazy" alt="' + esc(name) + '" src="' + esc(src) + '?width=640">';
}
function sentence(r) {
  const kind = (r[6] || CATLAB[r[1]] || "place").toLowerCase();
  const art = /^[aeiou]/.test(kind) ? "An" : "A";
  let s = art + " " + kind + (r[5] ? " in " + r[5] : (" in " + (DESTS[r[7]] ? DESTS[r[7]][1] : "the index"))) + ".";
  if (r[1] === "beach") {
    const side = r[2] >= MIDLAT[r[7]] ? "north" : "south";
    s = art + " " + kind + " on the " + side + " coast" + (r[5] ? " near " + r[5] : "")
      + ", at " + r[2].toFixed(3) + ", " + r[3].toFixed(3) + ".";
  }
  if (r[9]) s += " " + r[9] + ".";
  const have = []; if (r[10]) have.push("a phone number"); if (r[8]) have.push("a website");
  if (have.length) s += " The listing carries " + have.join(" and ") + ".";
  s += r[1] === "beach" ? " No colour measurement has been taken here."
                        : " Indexed from open map data and not yet scored.";
  return s;
}
function scoredCard(p, img) {
  const a = document.createElement("article"); a.className = "scored";
  a.innerHTML = photoEl(img, p.n)
    + '<div class="bd"><div class="ttl"><h3>' + esc(p.n) + "</h3>"
    + '<span class="total">' + String(tot(p)).replace(/\.0$/, "") + "<i>/30</i></span></div>"
    + '<p class="desc">' + esc(p.t) + "</p>"
    + '<div class="row" style="gap:5px">'
    + (p.ok ? '<span class="tag ok">Measured on site</span>' : '<span class="tag">Scored from evidence</span>')
    + (weak(p) ? '<span class="tag c">Cut — weak link</span>' : "")
    + '<span class="tag">' + CATLAB[p.c] + "</span></div>"
    + '<div class="scores"><span class="sc' + (p.D < 7 ? " weak" : "") + '">D ' + p.D + "</span>"
    + '<span class="sc' + (p.C < 7 ? " weak" : "") + '">C ' + p.C + "</span>"
    + '<span class="sc' + (p.W < 7 ? " weak" : "") + '">W ' + p.W + "</span>"
    + (p.hex ? '<span class="sc" title="Measured from photographs">hue ' + p.hue + "° sat " + p.sat + "</span>" : "")
    + "</div></div>";
  a.querySelector(".bd").appendChild(revBlock(p.n, p.d, p.D));
  return a;
}
function plainCard(r) {
  const a = document.createElement("article");
  a.innerHTML = photoEl(r[12], r[0])
    + '<div class="bd"><div class="ttl"><h3>' + esc(r[0]) + '</h3><span class="total"><i>unscored</i></span></div>'
    + '<div class="meta">' + esc(r[6] || CATLAB[r[1]] || "Place") + (r[5] ? " &middot; " + esc(r[5]) : "") + "</div>"
    + '<p class="desc">' + esc(sentence(r)) + "</p>"
    + (r[8] ? '<a class="site" href="' + esc(r[8]) + '" target="_blank" rel="noopener">'
        + esc(r[8].replace(/^https?:\/\//, "").replace(/\/$/, "")).slice(0, 46) + "</a>" : "")
    + '<div class="scores"><span class="sc" title="Drafted from place density, not measured">D ' + r[11] + " auto</span>"
    + '<span class="tag">' + (r[1] === "beach" ? "No colour measured" : "Colour unmeasured") + "</span></div></div>";
  a.querySelector(".bd").appendChild(revBlock(r[0], r[7], r[11]));
  return a;
}
const imgFor = (name, d) => {
  const hit = DATA.find(r => r[7] === d && r[12] && r[0].toLowerCase().includes(name.toLowerCase().split(" ")[0]));
  return hit ? hit[12] : "";
};

/* ---------- render ---------- */
function render() {
  const counts = {all:0};
  DATA.forEach(r => { if (r[7] === dest && r[1] !== "guide") { counts.all++; counts[r[1]] = (counts[r[1]] || 0) + 1; } });
  chips($("dests"), DESTS, dest, v => { dest = v; shown = 48; render(); });
  chips($("cats"), CATS, cat, v => { cat = v; shown = 48; render(); }, counts);
  const term = q.trim().toLowerCase();
  const sc = SCORED.filter(p => p.d === dest).filter(p => cat === "all" || p.c === cat)
    .filter(p => !term || (p.n + " " + p.t).toLowerCase().includes(term)).sort((a, b) => tot(b) - tot(a));
  const pl = DATA.filter(r => r[7] === dest && r[1] !== "guide")
    .filter(r => cat === "all" || r[1] === cat)
    .filter(r => !term || (r[0] + " " + r[6] + " " + r[5]).toLowerCase().includes(term))
    .filter(r => !sc.some(p => p.n.toLowerCase() === r[0].toLowerCase()));
  const g = $("grid"); g.innerHTML = "";
  sc.forEach(p => g.appendChild(scoredCard(p, imgFor(p.n, p.d))));
  pl.slice(0, Math.max(0, shown - sc.length)).forEach(r => g.appendChild(plainCard(r)));
  if (!sc.length && !pl.length) {
    g.innerHTML = '<div class="empty"><strong>Nothing indexed here yet</strong>This filter is live and empty for '
      + DESTS[dest][1] + ". Entries appear when the data covers them, or when somebody goes and measures.</div>";
  }
  $("count").textContent = fmt(sc.length + pl.length) + " places · " + sc.length
    + " verified · " + fmt(pl.length) + " awaiting measurement";
  const left = pl.length - Math.max(0, shown - sc.length);
  $("more").innerHTML = left > 0
    ? '<button class="more-btn" type="button">Show ' + fmt(Math.min(left, 96)) + " more of " + fmt(left) + "</button>" : "";
  const mb = $("more").querySelector("button"); if (mb) mb.onclick = () => { shown += 96; render(); };
}
function renderGuides() {
  const counts = {}; DESTS.forEach(([v]) => counts[v] = DATA.filter(r => r[7] === v && r[1] === "guide").length);
  chips($("gdests"), DESTS, gdest, v => { gdest = v; gshown = 36; renderGuides(); }, counts);
  const list = DATA.filter(r => r[7] === gdest && r[1] === "guide");
  const g = $("ggrid"); g.innerHTML = "";
  list.slice(0, gshown).forEach(r => {
    const a = document.createElement("article");
    a.innerHTML = '<div class="bd"><div class="ttl"><h3>' + esc(r[0]) + '</h3><span class="total"><i>prospect</i></span></div>'
      + '<div class="meta">' + esc(r[6] || "Operator") + (r[5] ? " &middot; " + esc(r[5]) : "") + "</div>"
      + '<p class="desc">' + esc(sentence(r)) + "</p>"
      + (r[8] ? '<a class="site" href="' + esc(r[8]) + '" target="_blank" rel="noopener">'
          + esc(r[8].replace(/^https?:\/\//, "").replace(/\/$/, "")).slice(0, 46) + "</a>"
        : '<div class="meta">No website in the data</div>')
      + '<div class="scores"><span class="tag">Not a customer</span></div></div>';
    g.appendChild(a);
  });
  $("gcount").textContent = fmt(list.length) + " operators already working in " + DESTS[gdest][1] + " · 0 signed";
  const left = list.length - gshown;
  $("gmore").innerHTML = left > 0
    ? '<button class="more-btn" type="button">Show ' + fmt(Math.min(left, 96)) + " more of " + fmt(left) + "</button>" : "";
  const mb = $("gmore").querySelector("button"); if (mb) mb.onclick = () => { gshown += 96; renderGuides(); };
}
function renderStatic() {
  $("acc").innerHTML = ACC.map(r => "<tr><td>" + esc(r[0]) + '</td><td style="color:var(--ink-soft)">' + esc(r[1])
    + '</td><td class="num">' + r[2] + '</td><td class="num">' + r[3] + '</td><td class="num" style="color:'
    + (r[4] === "0" ? "var(--ok)" : (Math.abs(parseFloat(r[4])) >= 2 ? "var(--cut)" : "var(--ink-soft)")) + '">' + r[4] + "</td></tr>").join("");
  $("auto").innerHTML = AUTO.map(r => "<tr><td>" + esc(r[0]) + '</td><td class="num">' + r[1] + '</td><td class="num">' + r[2]
    + '</td><td class="num" style="color:' + (r[3] === "0" ? "var(--ok)" : (Math.abs(parseFloat(r[3])) >= 2 ? "var(--cut)" : "var(--ink-soft)")) + '">' + r[3] + "</td></tr>").join("");
  const cats = CATS.filter(c => c[0] !== "all").concat([["guide","Guides & operators"]]);
  $("cov").innerHTML = cats.map(([k, l]) => {
    const a = DATA.filter(r => r[7] === 0 && r[1] === k).length;
    const b = DATA.filter(r => r[7] === 1 && r[1] === k).length;
    const s = SCORED.filter(p => p.c === k).length;
    const ph = DATA.filter(r => r[1] === k && r[12]).length;
    return "<tr><td>" + esc(l) + '</td><td class="num">' + fmt(a) + '</td><td class="num">' + fmt(b)
      + '</td><td class="num" style="color:' + (s ? "var(--accent)" : "var(--ink-faint)") + '">' + (s || "—")
      + '</td><td class="num">' + (ph || "—") + "</td></tr>";
  }).join("");
}

const TABS = [["t-dest","p-dest"],["t-guides","p-guides"],["t-acc","p-acc"],["t-cov","p-cov"]];
TABS.forEach(([tb, pn]) => $(tb).addEventListener("click", () => {
  TABS.forEach(([t2, p2]) => { $(t2).setAttribute("aria-selected", String(t2 === tb)); $(p2).hidden = (p2 !== pn); });
}));
$("q").addEventListener("input", e => { q = e.target.value; shown = 48; render(); });

loadReviews().then(() => fetch("data.json")).then(r => r.json()).then(j => {
  DATA = j.r;
  $("s-total").textContent = fmt(DATA.length);
  $("s-scored").textContent = SCORED.length;
  $("s-pic").textContent = fmt(DATA.filter(r => r[12]).length);
  render(); renderGuides(); renderStatic();
}).catch(() => {
  $("count").textContent = "Index did not load.";
  $("grid").innerHTML = '<div class="empty"><strong>Index did not load</strong>data.json could not be fetched. Serve this folder over HTTP rather than opening the file directly.</div>';
});
