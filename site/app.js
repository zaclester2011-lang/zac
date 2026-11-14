/* Hidden Water Index — destination packs.
   packs.json holds one row per destination; d/<id>.json is fetched when a pack opens. */

const COMMONS = "https://commons.wikimedia.org/wiki/Special:FilePath/";
const F = {N:0, C:1, LAT:2, LON:3, Q:4, LOC:5, KIND:6, WEB:7, AD:8, IMG:9, STARS:10};
const CATS = [["all","Everything"],["beach","Beaches"],["adventure","Adventures"],["food","Restaurants"],
  ["club","Bars & clubs"],["todo","Things to do"],["hotel","Hotels"],["indoor","Indoor"],["shop","Shops"]];
const CATLAB = {beach:"Beach", food:"Restaurant", club:"Bar or club", todo:"Thing to do",
  indoor:"Indoor", hotel:"Hotel", shop:"Shop", guide:"Guide", adventure:"Adventure"};

/* verified by standing in it */
const SCORED = {
  "seitan limania": {D:8, C:8.5, W:10, t:"A cleft in the limestone at the end of a dirt track. Deep off the shingle, with rock high enough to jump from."},
  "katholiko": {D:8.5, C:7.5, W:10, t:"Two kilometres down the Avlaki ravine past an 11th-century monastery cut into the cliff. No beach — entry is off stone."},
  "glyka nera": {D:7.5, C:8, W:10, t:"Thirty minutes along the coast path from Chora Sfakion. Freshwater springs rise through the shingle and cool the whole bay."},
  "preveli": {D:7, C:8, W:10, t:"Where the Kourtaliotiko river meets the Libyan Sea under a palm grove. The grove burned in July 2026."},
  "elafonissi": {D:6, C:9, W:10, t:"Pink shell sand on the south-west tip, shallow enough to stand a hundred metres out. Famous, and cut on Discovery once walked."},
  "balos": {D:6, C:9.5, W:10, t:"A sandbar between a lagoon and the open sea. The highest colour measured in Crete, and cut: a car park above, umbrella rows below."}
};

/* plain words → filters */
const WORD_CAT = {
  beach:"beach", beaches:"beach", sand:"beach", sea:"beach", swim:"beach", swimming:"beach",
  cove:"beach", lagoon:"beach", shore:"beach", coast:"beach", water:"beach", turquoise:"beach",
  bay:"beach", snorkel:"beach",
  bar:"club", bars:"club", club:"club", clubs:"club", nightclub:"club", nightlife:"club",
  pub:"club", drink:"club", drinks:"club", cocktail:"club", cocktails:"club", rooftop:"club",
  eat:"food", food:"food", restaurant:"food", restaurants:"food", dinner:"food", lunch:"food",
  breakfast:"food", taverna:"food", cafe:"food", coffee:"food", pizza:"food", seafood:"food",
  hotel:"hotel", hotels:"hotel", stay:"hotel", sleep:"hotel", room:"hotel", rooms:"hotel",
  resort:"hotel", villa:"hotel", hostel:"hotel",
  dive:"adventure", diving:"adventure", snorkelling:"adventure", hike:"adventure",
  hiking:"adventure", trek:"adventure", kayak:"adventure", boat:"adventure", sail:"adventure",
  sailing:"adventure", surf:"adventure", surfing:"adventure", climb:"adventure",
  climbing:"adventure", adventure:"adventure", trail:"adventure",
  museum:"indoor", gallery:"indoor", indoor:"indoor", inside:"indoor", rain:"indoor",
  rainy:"indoor", cinema:"indoor", theatre:"indoor", spa:"indoor",
  ancient:"todo", ruins:"todo", ruin:"todo", historic:"todo", history:"todo", temple:"todo",
  castle:"todo", monastery:"todo", gorge:"todo", canyon:"todo", waterfall:"todo", cave:"todo",
  viewpoint:"todo", view:"todo", mountain:"todo", archaeological:"todo", church:"todo",
  shop:"shop", shops:"shop", market:"shop", markets:"shop", shopping:"shop"
};
const QUIET = ["empty","hidden","quiet","remote","alone","secret","deserted","secluded",
               "unspoilt","wild","undiscovered","peaceful","nobody","untouched"];
const BUSY = ["busy","popular","famous","lively","crowded","buzzing","known"];
const STOP = ["a","an","the","in","on","at","with","somewhere","some","place","places","me","body",
              "i","want","find","show","to","for","of","and","that","where","can","is","it","my","we","best"];

function parseQuery(term) {
  const words = (term || "").toLowerCase().split(/[^a-z0-9']+/).filter(Boolean);
  const cats = new Set(); let minD = null, maxD = null; const rest = [];
  words.forEach(w => {
    if (STOP.includes(w)) return;
    if (WORD_CAT[w]) { cats.add(WORD_CAT[w]); return; }
    if (QUIET.includes(w)) { minD = 7.0; return; }
    if (BUSY.includes(w)) { maxD = 5; return; }
    rest.push(w);
  });
  return {cats, minD, maxD, words: rest, raw: (term || "").trim()};
}
function describe(p) {
  const bits = [];
  if (p.cats.size) bits.push([...p.cats].map(c => CATLAB[c] || c).join(", "));
  if (p.minD !== null) bits.push("Discovery " + p.minD + "+");
  if (p.maxD !== null) bits.push("Discovery " + p.maxD + " or under");
  if (p.words.length) bits.push('"' + p.words.join(" ") + '"');
  return bits.join(" · ");
}
function rowMatches(r, p) {
  if (p.cats.size && !p.cats.has(r[F.C])) return false;
  if (p.minD !== null && r[F.AD] < p.minD) return false;
  if (p.maxD !== null && r[F.AD] > p.maxD) return false;
  if (!p.words.length) return true;
  const hay = (r[F.N] + " " + (r[F.KIND]||"") + " " + (r[F.LOC]||"") + " " + (CATLAB[r[F.C]]||"")).toLowerCase();
  return p.words.every(w => hay.includes(w));
}

/* ---------------------------------------------------------------- state */
let PACKS = [], LOADED = {}, open_id = null, continent = "all";
let packQ = "", packCat = "all", shown = 60;
const $ = id => document.getElementById(id);
const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, m => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[m]));
const fmt = n => (n || 0).toLocaleString("en-GB");
const img = (file, alt, cls) => file
  ? '<img class="' + cls + '" loading="lazy" alt="' + esc(alt) + '" src="' + esc(COMMONS + encodeURIComponent(file) + "?width=480") + '">'
  : '<div class="' + cls + ' noimg"><span>No photograph yet</span></div>';
const scoredFor = name => {
  const n = (name || "").toLowerCase();
  for (const k in SCORED) if (n.includes(k)) return SCORED[k];
  return null;
};

/* ---------------------------------------------------------------- home */
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

function rankPacks(query) {
  const p = parseQuery(query);
  const useHidden = p.minD !== null;
  return PACKS.map(k => {
    let score;
    if (!p.cats.size && !useHidden) score = k.photos;
    else {
      const src = useHidden ? k.hidden : k.counts;
      const cats = p.cats.size ? [...p.cats] : Object.keys(src);
      score = cats.reduce((a, c) => a + (src[c] || 0), 0);
    }
    return {pack: k, score, parsed: p};
  }).filter(x => x.score > 0 || !query.trim())
    .sort((a, b) => b.score - a.score);
}

function renderHome() {
  const where = $("where").value.trim().toLowerCase();
  const want = $("want").value;
  const conts = ["all", ...Array.from(new Set(PACKS.map(p => p.continent))).sort()];
  chips($("conts"), conts.map(c => [c, c === "all" ? "Everywhere" : c]), continent,
        v => { continent = v; renderHome(); });

  let ranked = rankPacks(want);
  if (continent !== "all") ranked = ranked.filter(x => x.pack.continent === continent);
  if (where) ranked = ranked.filter(x => x.pack.name.toLowerCase().includes(where)
                                      || x.pack.continent.toLowerCase().includes(where));
  const p = parseQuery(want);
  const hint = want.trim() ? describe(p) : "";
  $("homecount").textContent = ranked.length + (ranked.length === 1 ? " destination" : " destinations")
    + (hint ? " · ranked by " + hint : "") ;

  const g = $("packs"); g.innerHTML = "";
  if (!ranked.length) {
    g.innerHTML = '<div class="empty"><strong>Nothing matches</strong>Try a place name, or a plain description like "hidden water body".</div>';
    return;
  }
  ranked.forEach(({pack, score, parsed}) => {
    const a = document.createElement("article"); a.className = "pack";
    const note = want.trim()
      ? '<div class="packscore">' + fmt(score) + " matching</div>" : "";
    a.innerHTML = img(pack.hero, pack.name, "packimg")
      + '<div class="packbody">'
      + '<div class="packtop"><h3>' + esc(pack.name) + "</h3>" + note + "</div>"
      + '<div class="meta">' + esc(pack.continent) + " · " + fmt(pack.places) + " places · "
      + fmt(pack.photos) + " photographs</div>"
      + '<div class="strip">' + pack.top.slice(0, 5).map(t =>
          '<span class="pill">' + esc(t.n.length > 22 ? t.n.slice(0, 21) + "…" : t.n) + "</span>").join("")
      + "</div></div>";
    a.onclick = () => openPack(pack.id);
    g.appendChild(a);
  });
}

/* ---------------------------------------------------------------- pack */
function openPack(id) {
  open_id = id; packQ = ""; packCat = "all"; shown = 60;
  $("home").hidden = true; $("pack").hidden = false;
  window.scrollTo(0, 0);
  const pk = PACKS.find(p => p.id === id);
  $("packname").textContent = pk.name;
  $("packmeta").textContent = pk.continent + " · " + fmt(pk.places) + " places · "
    + fmt(pk.photos) + " photographs";
  $("packhero").innerHTML = img(pk.hero, pk.name, "heroimg");
  $("topten").innerHTML = pk.top.map((t, i) => {
    const sc = scoredFor(t.n);
    return '<article class="top">' + img(t.img, t.n, "topimg")
      + '<div class="topbody"><div class="topnum">' + (i + 1) + "</div>"
      + "<h4>" + esc(t.n) + "</h4>"
      + '<div class="meta">' + esc(t.k || CATLAB[t.c] || "") + (t.loc ? " · " + esc(t.loc) : "") + "</div>"
      + (sc ? '<p class="desc">' + esc(sc.t) + "</p>"
            + '<div class="scores"><span class="sc">D ' + sc.D + '</span><span class="sc">C ' + sc.C
            + '</span><span class="sc">W ' + sc.W + "</span></div>"
          : '<div class="scores"><span class="sc">D ' + t.ad + " auto</span></div>")
      + "</div></article>";
  }).join("");
  $("packlist").innerHTML = "";
  $("packcount").textContent = "Loading " + pk.name + "…";
  loadPack(id).then(renderPack);
}
function loadPack(id) {
  if (LOADED[id]) return Promise.resolve(LOADED[id]);
  return fetch("d/" + id + ".json")
    .then(r => { if (!r.ok) throw new Error("d/" + id + ".json returned " + r.status); return r.json(); })
    .then(j => { LOADED[id] = j.r; return j.r; })
    .catch(err => {
      $("packcount").textContent = "Could not load: " + err.message;
      return [];
    });
}
function renderPack() {
  const rows = LOADED[open_id] || [];
  const counts = {all: 0};
  rows.forEach(r => { if (r[F.C] !== "guide") { counts.all++; counts[r[F.C]] = (counts[r[F.C]] || 0) + 1; } });
  chips($("packcats"), CATS, packCat, v => { packCat = v; shown = 60; renderPack(); }, counts);
  const p = packQ.trim() ? parseQuery(packQ) : null;
  let list = rows.filter(r => r[F.C] !== "guide")
    .filter(r => packCat === "all" || r[F.C] === packCat)
    .filter(r => !p || rowMatches(r, p));
  if (p && p.minD !== null) list.sort((a, b) => b[F.AD] - a[F.AD]);
  else list.sort((a, b) => ((b[F.IMG] ? 1 : 0) - (a[F.IMG] ? 1 : 0)) || (b[F.Q] - a[F.Q]));
  $("packcount").textContent = fmt(list.length) + " places"
    + (p && describe(p) ? " · " + describe(p) : "");
  const g = $("packlist"); g.innerHTML = "";
  if (!list.length) {
    g.innerHTML = '<div class="empty"><strong>Nothing here</strong>Try another word, or a category above.</div>';
  }
  list.slice(0, shown).forEach(r => {
    const sc = scoredFor(r[F.N]);
    const a = document.createElement("article");
    a.innerHTML = img(r[F.IMG], r[F.N], "cardimg")
      + '<div class="cardbody"><h4>' + esc(r[F.N]) + "</h4>"
      + '<div class="meta">' + esc(r[F.KIND] || CATLAB[r[F.C]] || "") + (r[F.LOC] ? " · " + esc(r[F.LOC]) : "") + "</div>"
      + (sc ? '<p class="desc">' + esc(sc.t) + "</p>" : "")
      + '<div class="scores">'
      + (r[F.STARS] ? '<span class="sc star">' + esc(r[F.STARS]) + "★</span>" : "")
      + (sc ? '<span class="sc">D ' + sc.D + '</span><span class="sc">C ' + sc.C + "</span>"
            : '<span class="sc">D ' + r[F.AD] + " auto</span>")
      + "</div>"
      + (r[F.WEB] ? '<a class="site" href="' + esc(r[F.WEB]) + '" target="_blank" rel="noopener">'
          + esc(r[F.WEB].replace(/^https?:\/\//, "").replace(/\/$/, "").slice(0, 40)) + "</a>" : "")
      + "</div>";
    g.appendChild(a);
  });
  const left = list.length - shown;
  $("packmore").innerHTML = left > 0
    ? '<button class="more-btn" type="button">Show ' + fmt(Math.min(left, 120)) + " more of " + fmt(left) + "</button>" : "";
  const mb = $("packmore").querySelector("button");
  if (mb) mb.onclick = () => { shown += 120; renderPack(); };
}

/* ---------------------------------------------------------------- wiring */
$("back").onclick = () => { $("pack").hidden = true; $("home").hidden = false; open_id = null; window.scrollTo(0, 0); };
$("where").addEventListener("input", renderHome);
$("want").addEventListener("input", renderHome);
$("packq").addEventListener("input", e => { packQ = e.target.value; shown = 60; renderPack(); });

fetch("packs.json").then(r => r.json()).then(j => {
  PACKS = j;
  $("s-dest").textContent = PACKS.length;
  $("s-places").textContent = fmt(PACKS.reduce((a, p) => a + p.places, 0));
  $("s-photos").textContent = fmt(PACKS.reduce((a, p) => a + p.photos, 0));
  renderHome();
}).catch(err => {
  $("homecount").textContent = "Could not load the destinations: " + err.message;
});
