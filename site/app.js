/* Hidden Water Index — destination packs.
   packs.json holds one row per destination; d/<id>.json is fetched when a pack opens. */

const COMMONS = "https://commons.wikimedia.org/wiki/Special:FilePath/";
const F = {N:0, C:1, LAT:2, LON:3, Q:4, LOC:5, KIND:6, WEB:7, AD:8, IMG:9, STARS:10, COL:11,
           CREDIT:12, N5:13, N2:14, NC:15, D:16};
/* "Shops" is gone: the clean-up left eleven places in it, and they were markets,
   which belong with things to do. */
const CATS = [["all","Everything"],["beach","Beaches"],["adventure","Adventures"],["food","Restaurants"],
  ["club","Bars & clubs"],["todo","Things to do"],["hotel","Hotels"],["indoor","Indoor"]];
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

/* "quiet" and "busy" used to move a Discovery floor. Discovery is gone, so they
   now work off what is mapped around a place, which is what they always meant. */
const QUIET_N2 = 40, BUSY_N2 = 200;

function parseQuery(term) {
  const words = (term || "").toLowerCase().split(/[^a-z0-9']+/).filter(Boolean);
  const cats = new Set(); let quiet = false, busy = false; const rest = [];
  words.forEach(w => {
    if (STOP.includes(w)) return;
    if (WORD_CAT[w]) { cats.add(WORD_CAT[w]); return; }
    if (QUIET.includes(w)) { quiet = true; return; }
    if (BUSY.includes(w)) { busy = true; return; }
    rest.push(w);
  });
  return {cats, quiet, busy, words: rest, raw: (term || "").trim()};
}
function describe(p) {
  const bits = [];
  if (p.cats.size) bits.push([...p.cats].map(c => CATLAB[c] || c).join(", "));
  if (p.quiet) bits.push("with little around them");
  if (p.busy) bits.push("in the thick of it");
  if (p.words.length) bits.push('"' + p.words.join(" ") + '"');
  return bits.join(" · ");
}
function rowMatches(r, p) {
  if (p.cats.size && !p.cats.has(r[F.C])) return false;
  const n2 = r[F.N2] || 0;
  if (p.quiet && n2 > QUIET_N2) return false;
  if (p.busy && n2 < BUSY_N2) return false;
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
/* the page serves its own pictures: artifacts refuse images from other hosts */
/* Grid pictures ride in sprite sheets: an artifact may publish 511 files, and
   there are 9,530 photographs, so one file per place was never possible. A cell
   reference looks like "pk/s0_1.jpg|37" — sheet, then which of its 256 cells. */
const SPRITE_COLS = 12, SPRITE_ROWS = 8;

const img = (file, alt, cls, credit) => {
  if (!file) {
    return '<div class="' + cls + ' noimg"><span>'
         + (credit ? "On Commons, not bundled here" : "No photograph") + "</span></div>";
  }
  const bar = file.indexOf("|");
  if (bar > 0) {
    const sheet = file.slice(0, bar), cell = +file.slice(bar + 1);
    const col = cell % SPRITE_COLS, row = Math.floor(cell / SPRITE_COLS);
    return '<div class="' + cls + ' sprite" role="img" aria-label="' + esc(alt) + '" style="'
         + "background-image:url(" + esc(sheet) + ");"
         + "background-size:" + SPRITE_COLS * 100 + "% " + SPRITE_ROWS * 100 + "%;"
         + "background-position:" + (col * 100) / (SPRITE_COLS - 1) + "% "
         + (row * 100) / (SPRITE_ROWS - 1) + '%"></div>';
  }
  const src = file.indexOf("/") >= 0 ? file : "img/" + file;
  const back = credit ? COMMONS + encodeURIComponent(String(credit).replace(/ /g, "_")) + "?width=480" : "";
  return '<img class="' + cls + '" loading="lazy" alt="' + esc(alt) + '" src="' + esc(src)
       + '" data-back="' + esc(back) + '" data-cls="' + cls + '">';
};
/* one handler for every picture: try the cached copy, then Commons, then a plain panel */
document.addEventListener("error", function (e) {
  const el = e.target;
  if (!el || el.tagName !== "IMG" || !el.dataset) return;
  if (el.dataset.back && !el.dataset.tried) { el.dataset.tried = "1"; el.src = el.dataset.back; return; }
  const d = document.createElement("div");
  d.className = (el.dataset.cls || "") + " noimg";
  d.innerHTML = "<span>Photograph unavailable</span>";
  if (el.parentNode) el.parentNode.replaceChild(d, el);
}, true);

/* a name for a measured hue \u2014 never written without the numbers beside it */
// Colour is a rating of water, so it only applies where water is the point of
// the place. Kept in step with tools/rate.py, which decides the same question
// when the ratings are written: the kind of thing it is settles it, and the
// name is only consulted when no kind was recorded.
const WATERY_KIND = /\b(beach|bay|cove|lagoon|lagoa|lake|pond|reservoir|river|stream|creek|waterfall|falls|cascade|spring|springs|geyser|gorge|canyon|cave|cenote|reef|island|islet|marina|harbour|harbor|pool|sea|ocean|coast|shore|cliff|fjord|strait|waterway|dam|wetland|water park|dive|diving|scuba|snorkel|snorkeling|surf|surfing|kayak|canoe|paddle|raft|rafting|fishing|boat|sail|sailing|cruise|swim|swimming)\b/i;
const DRY_KIND = /\b(parking|playground|skate|dog park|amusement|historic|monument|memorial|museum|church|temple|mosque|synagogue|worship|religious|school|library|hotel|restaurant|cafe|shop|store|office|hospital|government|cemetery|stadium|golf|zoo|theatre|theater|cinema|hiking|climbing|equestrian|horse)\b/i;
const WATERY_NAME = /\b(beach|bay|cove|lagoon|lake|river|waterfall|cascade|spring|gorge|canyon|cave|reef|island|islet|harbour|harbor|marina|pool|sea|coast|shore|strand|playa|spiaggia|cala|paralia|limni|akti|falls|creek|delta|estuary|fjord|sandbar|peninsula|cape|lido|plage|praia)\b/i;

function isWatery(cat, kind, name) {
  if (cat === "beach") return true;
  if (cat !== "adventure" && cat !== "todo") return false;
  const k = kind || "";
  if (DRY_KIND.test(k)) return false;
  if (WATERY_KIND.test(k)) return true;
  if (!k.trim()) return WATERY_NAME.test(name || "");
  return false;
}

function shade(h, s) {
  if (s < 0.22) return "washed-out and grey-leaning";
  if (h < 160) return "green";
  if (h < 168) return "green-leaning turquoise";
  if (h <= 195) return "turquoise";
  if (h <= 205) return "clear blue";
  if (h <= 215) return "deep blue";
  return "flat navy";
}

/* How busy it looks from the map, in words. The counts are the evidence. */
function company(n5, n2) {
  if (n5 === 0 && n2 <= 2) return "nothing else is mapped within two kilometres of it";
  if (n5 === 0) return "nothing else is mapped within five hundred metres";
  if (n5 <= 3) return "barely anything stands within five hundred metres";
  if (n5 <= 15) return "a handful of other places stand within five hundred metres";
  if (n5 <= 60) return "it sits among dozens of others";
  return "it stands in the middle of a crowd";
}

/* What a place is, and why it is worth going to. Nothing else.
   No coordinates: nobody reads a card to learn a decimal degree. */
function paragraph(r) {
  const kind = (r[F.KIND] || CATLAB[r[F.C]] || "place").toLowerCase().replace(/_/g, " ");
  const art = /^[aeiou]/.test(kind) ? "an" : "a";
  const where = r[F.LOC] ? " in " + r[F.LOC] : "";
  const n5 = r[F.N5] || 0, n2 = r[F.N2] || 0, nc = r[F.NC] || 0;
  const out = [];

  // 1 \u2014 what it is, and where
  out.push(r[F.N] + " is " + art + " " + kind + where + ".");

  // 2 \u2014 the reason to go: the water where water is the point, the rating
  //     where somebody has rated it, and otherwise how quiet it stands
  const watery = isWatery(r[F.C], r[F.KIND], r[F.N]);
  const saidWater = watery && r[F.COL] && r[F.COL][0] != null;
  if (saidWater) {
    out.push("The water in its photograph is " + shade(r[F.COL][0], r[F.COL][1])
             + (r[F.COL][2] != null
                ? ", which I rate " + r[F.COL][2].toFixed(1) + " out of ten for colour."
                : ", though too little of the frame is water to put a number on it."));
  } else if (watery) {
    out.push("No photograph of it shows enough water to judge its colour.");
  }

  // 3 \u2014 how crowded a spot it stands in, which is the other half of the reason
  const peers = CATLAB[r[F.C]] ? CATLAB[r[F.C]].toLowerCase() + "s" : "places of its kind";
  if (nc > 4 && (r[F.C] === "food" || r[F.C] === "hotel" || r[F.C] === "club" || r[F.C] === "shop")) {
    out.push("It is one of " + fmt(nc + 1) + " " + peers + " within two kilometres"
             + (n5 <= 3 ? ", but barely anything stands within five hundred metres of it." : "."));
  } else {
    out.push(cap(company(n5, n2)) + ".");
  }

  // 4 \u2014 what people who went think of it
  if (r[F.STARS]) out.push("Visitors rate it " + r[F.STARS] + " out of five.");
  return out.join(" ");
}
const cap = s => s.charAt(0).toUpperCase() + s.slice(1);

/* The score badges. Discovery is gone at Zac's word, so Colour and Water carry
   the rating on their own. */
function ratings(r, sc) {
  if (sc) {
    return '<span class="sc meas" title="Measured standing in it">C ' + sc.C + "</span>"
         + '<span class="sc meas" title="Sea is Water 10 always">W ' + sc.W + "</span>"
         + '<span class="sc tag">measured</span>';
  }
  const c = r[F.COL] && r[F.COL][2] != null ? r[F.COL][2] : null;
  let out = "";
  if (c != null) {
    out += '<span class="sc" title="My rating: measured from the water in its photograph">C '
         + c.toFixed(1) + "</span>";
  } else if (isWatery(r[F.C], r[F.KIND], r[F.N])) {
    // water is the point of this place, so a missing Colour is worth showing
    out += '<span class="sc none" title="Too little water in its photograph to rate">C —</span>';
  }
  return out;
}
const scoredFor = name => {
  const n = (name || "").toLowerCase();
  for (const k in SCORED) if (n.includes(k)) return SCORED[k];
  return null;
};

/* A paragraph for every destination, same rule: only facts the index holds. */
function destParagraph(k) {
  const out = [];
  out.push(k.name + " sits in " + k.continent + ", and the index holds " + fmt(k.places)
           + " places in it, " + fmt(k.photos) + " of them with a photograph.");
  const b = (k.counts && k.counts.beach) || 0;
  const hb = (k.quiet && k.quiet.beach) || 0;
  if (b) {
    out.push(fmt(b) + " are beaches" + (hb
      ? ", and " + fmt(hb) + " of those stand with almost nothing else mapped around them."
      : ", though every one of them sits in a crowd of other places: this is a busy coast."));
  } else {
    out.push("No beaches are mapped here yet.");
  }
  if (k.bestcol) {
    out.push("The best water I have rated in it is " + k.bestcol[0] + ", at Colour "
             + Number(k.bestcol[1]).toFixed(1) + " out of ten"
             + (k.rated ? ", out of " + fmt(k.rated) + " places whose water I could measure." : "."));
  } else {
    out.push("None of its photographs show enough water for me to rate Colour yet.");
  }
  return out.join(" ");
}

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

/* Typing anything must actually filter. Words that are not a category and not
   "quiet" or "busy" are matched against each destination's own search text —
   its name, its continent, and the names and kinds of the places in it — so
   "navagio", "cenote" or "windsurf" narrow the list instead of being ignored. */
function rankPacks(query) {
  const p = parseQuery(query);
  return PACKS.map(k => {
    const src = p.quiet ? (k.quiet || k.counts) : k.counts;
    let score;
    if (p.cats.size) score = [...p.cats].reduce((a, c) => a + (src[c] || 0), 0);
    else if (p.quiet || p.busy) score = Object.keys(src).reduce((a, c) => a + (src[c] || 0), 0);
    else score = k.photos;

    let ok = true;
    if (p.words.length) {
      const blob = k.blob || (k.name + " " + k.continent).toLowerCase();
      ok = p.words.every(w => blob.indexOf(w) >= 0);
      // a destination that names the thing beats one that is merely large
      if (ok) score += 100000;
    }
    return {pack: k, score, parsed: p, ok};
  }).filter(x => x.ok && (x.score > 0 || !query.trim()))
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
    a.innerHTML = img(pack.hero, pack.name, "packimg", pack.hero_title)
      + '<div class="packbody">'
      + '<div class="packtop"><h3>' + esc(pack.name) + "</h3>" + note + "</div>"
      + '<div class="meta">' + esc(pack.continent) + " · " + fmt(pack.places) + " places · "
      + fmt(pack.photos) + " photographs</div>"
      + '<p class="desc">' + esc(destParagraph(pack)) + "</p>"
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
  $("packhero").innerHTML = img(pk.hero, pk.name, "heroimg", pk.hero_title);
  $("topten").innerHTML = pk.top.map((t, i) => {
    const sc = scoredFor(t.n);
    return '<article class="top">' + img(t.img, t.n, "topimg", t.credit)
      + '<div class="topbody"><div class="topnum">' + (i + 1) + "</div>"
      + "<h4>" + esc(t.n) + "</h4>"
      + '<div class="meta">' + esc(t.k || CATLAB[t.c] || "") + (t.loc ? " · " + esc(t.loc) : "") + "</div>"
      + '<p class="desc">' + esc((sc ? sc.t + " " : "") + paragraph(t.row || [])) + "</p>"
      + '<div class="scores">' + ratings(t.row || [], sc) + "</div>"
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
  // asked for quiet, so the emptiest surroundings come first
  if (p && p.quiet) list.sort((a, b) => (a[F.N2] || 0) - (b[F.N2] || 0));
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
    a.innerHTML = img(r[F.IMG], r[F.N], "cardimg", r[F.CREDIT])
      + '<div class="cardbody"><h4>' + esc(r[F.N]) + "</h4>"
      + '<div class="meta">' + esc(r[F.KIND] || CATLAB[r[F.C]] || "") + (r[F.LOC] ? " · " + esc(r[F.LOC]) : "") + "</div>"
      + '<p class="desc">' + esc((sc ? sc.t + " " : "") + paragraph(r)) + "</p>"
      + '<div class="scores">'
      + (r[F.STARS] ? '<span class="sc star">' + esc(r[F.STARS]) + "★</span>" : "")
      + ratings(r, sc)
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
