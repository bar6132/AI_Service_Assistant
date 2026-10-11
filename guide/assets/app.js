/* App shell: routing, markdown-block renderer, quiz, read-aloud player. */
(function () {
  "use strict";
  const L = window.LESSONS || [];
  const $ = (s, r) => (r || document).querySelector(s);
  const main = $("#main");
  const store = {
    get(k, d) { try { const v = localStorage.getItem("guide." + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem("guide." + k, JSON.stringify(v)); } catch (e) { /* private mode */ } },
  };
  const H = window.GuideKit.h;

  /* ───────── inline markdown ───────── */
  const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  function inline(md) {
    let t = esc(md);
    t = t.replace(/`([^`]+)`/g, (m, c) => "<code>" + c + "</code>");
    t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    t = t.replace(/(^|[^*])\*([^*]+)\*(?!\*)/g, "$1<em>$2</em>");
    t = t.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
    t = t.replace(/([֐-׿][֐-׿\s"'.,!?()\-:;0-9A-Za-z]*[֐-׿]|[֐-׿])/g, "<bdi>$1</bdi>");
    return t;
  }

  /* ───────── tiny Python highlighter ───────── */
  const KW = new Set("def class return if elif else for while in not and or is None True False try except finally raise import from as with lambda pass break continue yield async await".split(" "));
  function highlight(code, lang) {
    if (lang !== "py" && lang !== "python") return esc(code);
    const re = /(#[^\n]*)|("""[\s\S]*?"""|"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*')|(@\w+)|\b([A-Za-z_]\w*)\b(?=\()|\b([A-Za-z_]\w*)\b/g;
    let out = "", last = 0, m;
    while ((m = re.exec(code))) {
      out += esc(code.slice(last, m.index));
      if (m[1]) out += '<span class="c">' + esc(m[1]) + "</span>";
      else if (m[2]) out += '<span class="s">' + esc(m[2]) + "</span>";
      else if (m[3]) out += '<span class="d">' + esc(m[3]) + "</span>";
      else if (m[4]) out += KW.has(m[4]) ? '<span class="k">' + m[4] + "</span>" : '<span class="f">' + m[4] + "</span>";
      else if (m[5]) out += KW.has(m[5]) ? '<span class="k">' + m[5] + "</span>" : esc(m[5]);
      last = re.lastIndex;
    }
    return out + esc(code.slice(last));
  }

  /* ───────── block renderer ───────── */
  const CALLOUT = { eli5: "Like you're five", path: "The path we took", why: "Why we chose this", honest: "Honest note", watch: "Watch out" };
  let narrEls = []; // index n -> element

  function renderBlocks(lesson, root) {
    narrEls = [];
    lesson.blocks.forEach((b) => {
      let el;
      if (b.t === "h2") {
        el = H("h2", { class: "sec blk", html: inline(b.md) });
        track(el, b.n, root);
      } else if (b.t === "p") {
        el = H("p", { class: "blk", html: inline(b.md) });
        track(el, b.n, root);
      } else if (b.t === "callout") {
        el = H("div", { class: "callout " + b.kind }, H("span", { class: "lbl" }, CALLOUT[b.kind] || b.kind), H("p", { html: inline(b.md) }));
        track(el, b.n, root);
      } else if (b.t === "ul" || b.t === "ol") {
        el = H(b.t, { class: "blk" });
        b.items.forEach((it) => {
          const li = H("li", { html: inline(it.md) });
          el.appendChild(li);
          narrEls[it.n] = li;
          li.addEventListener("click", () => Player.playFrom(it.n));
        });
      } else if (b.t === "code") {
        el = H("div", { class: "codebox" },
          H("div", { class: "ct" }, H("span", {}, b.title || b.lang || "code"), H("span", {}, b.lang || "")),
          H("pre", { html: highlight(b.text, b.lang) }));
      } else if (b.t === "table") {
        const [head, ...rows] = b.rows;
        el = H("div", { class: "tbl-wrap" }, H("table", { class: "tbl" },
          H("thead", {}, H("tr", {}, ...head.map((c) => H("th", { html: inline(c) })))),
          H("tbody", {}, ...rows.map((r) => H("tr", {}, ...r.map((c) => H("td", { html: inline(c) })))))));
      } else if (b.t === "widget") {
        const w = window.GuideWidgets[b.name];
        el = H("section", { class: "widget", "data-role": lesson.role === "none" ? "code" : lesson.role });
        if (w) { try { w(el, { go }); } catch (e) { el.textContent = "Widget error: " + e.message; console.error(e); } }
        else el.textContent = "Missing widget: " + b.name;
      } else if (b.t === "quiz") {
        el = renderQuiz(lesson.id, b.questions);
      }
      if (el) root.appendChild(el);
    });
  }

  function track(el, n, root) {
    narrEls[n] = el;
    const btn = H("button", { class: "play-here", "aria-label": "Read from here", title: "Read from here" }, "▶");
    btn.addEventListener("click", (e) => { e.stopPropagation(); Player.playFrom(n); });
    el.style.position = "relative";
    el.appendChild(btn);
  }

  function renderQuiz(id, questions) {
    const saved = store.get("quiz." + id, null);
    const box = H("section", { class: "quiz" }, H("h3", {}, "Check yourself"));
    let answered = 0, right = 0;
    const score = H("p", { class: "score" });
    questions.forEach((q, qi) => {
      const wrap = H("div", { class: "q" }, H("p", {}, q.q));
      const why = H("p", { class: "why", hidden: true }, q.why);
      const labels = q.options.map((o, oi) => {
        const inp = H("input", { type: "radio", name: id + "q" + qi });
        const lab = H("label", {}, inp, H("span", { html: inline(o) }));
        inp.addEventListener("change", () => {
          if (wrap.dataset.done) return;
          wrap.dataset.done = "1";
          answered++;
          if (oi === q.answer) { right++; lab.classList.add("right"); } else { lab.classList.add("wrong"); labels[q.answer].classList.add("right"); }
          why.hidden = false;
          wrap.querySelectorAll("input").forEach((i) => (i.disabled = true));
          score.textContent = answered === questions.length ? "You got " + right + " of " + questions.length + (right === questions.length ? ". Chapter complete." : ". Reread the highlighted parts and try again later.") : "";
          if (answered === questions.length) store.set("quiz." + id, right);
        });
        wrap.appendChild(lab);
        return lab;
      });
      wrap.appendChild(why);
      box.appendChild(wrap);
    });
    if (saved != null) score.textContent = "Last score: " + saved + " of " + questions.length;
    box.appendChild(score);
    return box;
  }

  /* ───────── sidebar + routing ───────── */
  const track$ = $("#track");
  function buildTrack() {
    track$.innerHTML = "";
    const visited = store.get("visited", {});
    L.forEach((l, i) => {
      const a = H("a", { href: "#/" + l.id }, H("i", { class: "node" }, String(i)), H("span", {}, H("span", { class: "t-title" }, l.title), H("span", { class: "t-meta" }, l.station + " · " + l.minutes + " min")));
      const li = H("li", { "data-role": l.role, "data-id": l.id, class: visited[l.id] ? "visited" : "" }, a);
      track$.appendChild(li);
    });
  }
  function markCurrent(id) {
    track$.querySelectorAll("li").forEach((li) => li.classList.toggle("current", li.dataset.id === id));
  }
  function markVisited(id) {
    const v = store.get("visited", {}); v[id] = 1; store.set("visited", v);
    const li = track$.querySelector('[data-id="' + id + '"]'); if (li) li.classList.add("visited");
  }
  function go(id) { location.hash = "#/" + id; }

  function route() {
    Player.stop();
    document.body.classList.remove("menu-open");
    const id = (location.hash.replace(/^#\/?/, "") || "");
    const lesson = L.find((l) => l.id === id);
    main.innerHTML = "";
    window.scrollTo(0, 0);
    if (!lesson) { renderHome(); markCurrent(""); Player.load(null); return; }
    markCurrent(id);
    const i = L.indexOf(lesson);
    const page = H("article", { class: "page", "data-role": lesson.role });
    page.appendChild(H("header", { class: "ch-head" },
      H("span", { class: "ch-station" }, H("i", { class: "dot" }), lesson.station),
      H("h1", { class: "ch-title" }, lesson.title),
      H("p", { class: "ch-meta" }, "Chapter " + i + " of " + (L.length - 1) + " · about " + lesson.minutes + " minutes")));
    renderBlocks(lesson, page);
    const nav = H("div", { class: "hero-cta" });
    if (L[i - 1]) nav.appendChild(H("a", { class: "btn", href: "#/" + L[i - 1].id }, "Back: " + L[i - 1].title));
    if (L[i + 1]) nav.appendChild(H("a", { class: "btn solid", "data-role": L[i + 1].role, href: "#/" + L[i + 1].id }, "Next: " + L[i + 1].title));
    else nav.appendChild(H("a", { class: "btn", href: "#/" }, "Back to the start"));
    page.appendChild(nav);
    main.appendChild(page);
    document.title = lesson.title + " – Inside the Service";
    markVisited(id);
    Player.load(lesson, narrEls);
  }

  /* ───────── home ───────── */
  const DEMO_MSG = "I want to cancel order ORD-1001";
  const DEMO_ST = [
    ["Understand", "AI model", "model", "The model reads the message and fills a small form: intent cancel, order ORD-1001, language English."],
    ["Verify", "code", "code", "Code checks that ORD-1001 is really written in the message. It is, so it survives."],
    ["Look up", "code", "code", "Code fetches the order, and only because it belongs to this customer. Status: processing."],
    ["Decide", "code", "code", "The rulebook says: processing orders can get a cancellation request. Action: reply."],
    ["Record", "database", "db", "The database hands out the next number and stores the request: SR-000002."],
    ["Write", "AI model", "model", "The second model gets a card of facts and writes a polite note. It may not promise anything."],
    ["Inspect", "guard", "guard", "The guard reads the note. No forbidden words, no wrong dates, the request number is there. It passes."],
  ];
  let heroTimer = null;
  function renderHome() {
    document.title = "Inside the Service";
    const page = H("div", { class: "page wide hero" });
    page.appendChild(H("h1", {}, "Follow one message through the machine."));
    page.appendChild(H("p", { class: "lead" }, "A customer writes to an online shop. Seven small stations turn that sentence into a safe, honest answer. This guide shows each station, the road we took to build it, and why. Play with it, break it, and press play to hear it."));
    const rail = H("div", { class: "rail" }, H("div", { class: "fill" }));
    const sts = DEMO_ST.map((s) => {
      const el = H("div", { class: "st", "data-role": s[2] }, H("i", {}), s[0], H("small", {}, s[1]));
      rail.appendChild(el); return el;
    });
    const caption = H("p", { class: "caption" }, "The message is waiting at the first station.");
    const replay = H("button", { class: "btn" }, "Replay");
    page.appendChild(H("section", { class: "runway", "aria-label": "Animated demo of the seven stations" },
      H("div", { class: "msg-bubble msg" }, DEMO_MSG), rail, caption, H("div", { class: "row" }, replay)));
    function play() {
      clearTimeout(heroTimer);
      const fill = $(".fill", rail);
      sts.forEach((s) => s.classList.remove("lit"));
      fill.style.width = "0";
      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      let i = 0;
      (function step() {
        if (i >= DEMO_ST.length) return;
        sts[i].classList.add("lit");
        fill.style.width = (i / (DEMO_ST.length - 1)) * 86 + "%";
        caption.textContent = DEMO_ST[i][3];
        i++;
        heroTimer = setTimeout(step, reduce ? 1200 : 1900);
      })();
    }
    replay.addEventListener("click", play);
    setTimeout(play, 500);
    const cta = H("div", { class: "hero-cta" },
      H("a", { class: "btn solid", href: "#/" + L[0].id }, "Start the journey"),
      H("button", { class: "btn", id: "heroListen" }, "Listen to the intro"));
    page.appendChild(cta);
    cta.querySelector("#heroListen").addEventListener("click", () => go(L[0].id) || setTimeout(() => Player.toggle(), 400));
    page.appendChild(H("p", { class: "brand-sub", style: "margin-top:26px" }, "Colour tells you who is working: violet is the AI model, teal is plain code, amber is the database, red is the guard."));
    const grid = H("div", { class: "chapter-grid" });
    L.forEach((l, i) => grid.appendChild(H("a", { href: "#/" + l.id, "data-role": l.role }, H("b", {}, i + ". " + l.title), H("span", {}, l.station + " · " + l.minutes + " min"))));
    page.appendChild(grid);
    main.appendChild(page);
  }

  /* ───────── read-aloud player ───────── */
  const Player = (function () {
    const synth = window.speechSynthesis;
    const el = { play: $("#playBtn"), prev: $("#prevBtn"), next: $("#nextBtn"), title: $("#nowTitle"), sub: $("#nowSub"), bar: $("#progBar"), voice: $("#voiceSel"), rate: $("#rate"), auto: $("#auto") };
    let lesson = null, els = [], flat = [], idx = 0, playing = false, token = 0, audio = null, voices = [];

    el.rate.value = store.get("rate", 1); el.auto.checked = store.get("auto", false);

    function flatten(ls) {
      const out = [];
      ls.blocks.forEach((b) => { if (b.n != null) out[b.n] = b.say; if (b.items) b.items.forEach((it) => (out[it.n] = it.say)); });
      return out;
    }
    function loadVoices() {
      if (!synth) { el.voice.innerHTML = "<option>No browser voice</option>"; return; }
      voices = synth.getVoices().filter((v) => /^en/i.test(v.lang));
      const score = (v) => (/natural|online|neural/i.test(v.name) ? 0 : /google|microsoft/i.test(v.name) ? 1 : 2);
      voices.sort((a, b) => score(a) - score(b) || a.name.localeCompare(b.name));
      el.voice.innerHTML = "";
      voices.forEach((v, i) => el.voice.appendChild(H("option", { value: i }, v.name.replace(/Microsoft |Google /, "") + " (" + v.lang + ")")));
      const saved = store.get("voice", "");
      const si = voices.findIndex((v) => v.name === saved);
      if (si >= 0) el.voice.value = si;
    }
    if (synth) { loadVoices(); synth.addEventListener("voiceschanged", loadVoices); }
    el.voice.addEventListener("change", () => { const v = voices[el.voice.value]; if (v) store.set("voice", v.name); if (playing) speak(idx); });
    el.rate.addEventListener("input", () => { store.set("rate", +el.rate.value); });
    el.rate.addEventListener("change", () => { if (playing) speak(idx); });
    el.auto.addEventListener("change", () => store.set("auto", el.auto.checked));

    function setUi() {
      el.play.innerHTML = playing ? "&#10074;&#10074;" : "&#9654;";
      el.play.setAttribute("aria-label", playing ? "Pause" : "Read this chapter aloud");
    }
    function mark(i) {
      els.forEach((e) => e && e.classList.remove("speaking"));
      const e = els[i];
      if (e) { e.classList.add("speaking"); e.scrollIntoView({ block: "center", behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }); }
      const total = flat.length || 1;
      el.bar.style.width = ((i + 1) / total) * 100 + "%";
      el.sub.textContent = "Part " + (i + 1) + " of " + total;
    }
    function cancel() { token++; if (synth) synth.cancel(); if (audio) { audio.onended = audio.onerror = null; audio.pause(); audio = null; } }

    function speak(i) {
      cancel();
      if (!lesson || i >= flat.length) { finish(); return; }
      idx = i; playing = true; setUi(); mark(i);
      const my = token;
      const text = flat[i];
      if (!text) { speak(i + 1); return; }
      const next = () => { if (my === token) speak(i + 1); };
      const viaTts = () => {
        if (!synth) { el.title.textContent = "This browser has no speech voices"; playing = false; setUi(); return; }
        const u = new SpeechSynthesisUtterance(text);
        const v = voices[el.voice.value]; if (v) { u.voice = v; u.lang = v.lang; } else u.lang = "en-US";
        u.rate = +el.rate.value;
        u.onend = next; u.onerror = (e) => { if (e.error !== "canceled" && e.error !== "interrupted") next(); };
        synth.speak(u);
      };
      if (lesson.audio) {
        audio = new Audio("audio/" + lesson.id + "/" + i + "." + lesson.audio);
        audio.playbackRate = +el.rate.value;
        audio.onended = next; audio.onerror = () => { audio = null; if (my === token) viaTts(); };
        audio.play().catch(() => { audio = null; if (my === token) viaTts(); });
      } else viaTts();
    }
    function finish() {
      playing = false; setUi(); els.forEach((e) => e && e.classList.remove("speaking"));
      if (lesson && el.auto.checked) { const i = L.indexOf(lesson); if (L[i + 1]) { go(L[i + 1].id); setTimeout(() => Player.toggle(), 600); } }
    }
    return {
      load(ls, e) {
        lesson = ls; els = e || []; idx = 0; playing = false; setUi();
        flat = ls ? flatten(ls) : [];
        el.title.textContent = ls ? ls.title : "Press play on any chapter to hear it";
        el.sub.textContent = ls ? flat.length + " parts · " + (ls.audio ? "local AI voice" : "browser voice") : "";
        el.bar.style.width = "0";
      },
      stop() { cancel(); playing = false; setUi(); els.forEach((e) => e && e.classList.remove("speaking")); },
      toggle() {
        if (!lesson) { go(L[0].id); return; }
        if (playing) { cancel(); playing = false; setUi(); } else speak(idx);
      },
      playFrom(n) { if (lesson) speak(n); },
      index() { return idx; },
    };
  })();
  $("#playBtn").addEventListener("click", () => Player.toggle());
  $("#prevBtn").addEventListener("click", () => Player.playFrom(Math.max(0, Player.index() - 1)));
  $("#nextBtn").addEventListener("click", () => Player.playFrom(Player.index() + 1));

  /* ───────── chrome ───────── */
  $("#menuBtn").addEventListener("click", () => {
    const open = document.body.classList.toggle("menu-open");
    $("#menuBtn").setAttribute("aria-expanded", open);
  });
  $("#themeBtn").addEventListener("click", () => {
    const cur = document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const nxt = cur === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = nxt; store.set("theme", nxt);
  });
  $("#resetBtn").addEventListener("click", () => {
    if (!confirm("Clear your visited chapters and quiz scores?")) return;
    try { Object.keys(localStorage).filter((k) => k.indexOf("guide.") === 0 && !/theme|rate|voice|auto/.test(k)).forEach((k) => localStorage.removeItem(k)); } catch (e) { /* ignore */ }
    buildTrack(); route();
  });
  const savedTheme = store.get("theme", null); if (savedTheme) document.documentElement.dataset.theme = savedTheme;

  buildTrack();
  window.addEventListener("hashchange", route);
  route();
})();
