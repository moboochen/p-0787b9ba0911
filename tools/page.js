(function () {
  var DATA = JSON.parse(document.getElementById("payload").textContent);
  var LEGACY = ["pubsched_v2", "props_v1"];
  var DRAFT_KEY = "review_draft_v3";
  var TAB = "new";
  var ignored = [];
  LEGACY.forEach(function (k) {
    try { if (localStorage.getItem(k) != null) ignored.push(k); } catch (e) {}
  });

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function drafts() {
    try { return JSON.parse(localStorage.getItem(DRAFT_KEY) || "{}"); } catch (e) { return {}; }
  }
  function saveDrafts(d) {
    localStorage.setItem(DRAFT_KEY, JSON.stringify(d));
  }
  function draftApplies(current, stored) { return !!current && current === stored; }
  function taipeiDate() {
    return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Taipei", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
  }
  function inPublished(it) {
    if (it.section === "published") return true;
    if (it.section !== "cut") return false;
    return ["yt", "fb", "ig"].some(function (k) { return it.platforms && it.platforms[k] && it.platforms[k].published; });
  }
  function pool(tab) {
    return DATA.items.filter(function (it) {
      if (tab === "published") return inPublished(it);
      if (tab === "cut") return it.section === "cut";
      return it.section === tab;
    });
  }
  function flags(it) {
    var f = it.flags || {};
    function chip(name, on) { return '<span class="flag ' + (on ? "yes" : "no") + '">' + name + "：" + (on ? "是" : "否") + "</span>"; }
    return '<div class="flags">' + chip("選片", f.proposal_selected) + chip("腳本核准", f.script_approved) + chip("開剪", f.cut_authorized) + chip("發佈核准", f.publish_approved) + "</div>";
  }
  function platforms(it) {
    if (!it.platforms) return "";
    return '<div class="chips">' + ["yt", "fb", "ig"].map(function (k) {
      var p = it.platforms[k];
      if (p.published) return '<span class="chip on">' + esc(p.label) + " 已發佈 " + esc(p.date || "") + " " + esc(p.source || "") + "</span>";
      var extra = p.source ? "（" + p.source + "）" : "";
      return '<span class="chip off">' + esc(p.label) + " 未發" + esc(extra) + "</span>";
    }).join("") + "</div>";
  }
  var QCNAME = { not_run: "未跑", absent: "沒有台帳", stale: "身份不符", fail: "失敗", pass: "通過", warn_unaccepted: "警告未接受", warn_accepted: "警告已接受", not_pass: "未通過" };
  function qcName(state) { return QCNAME[state] || state || "沒有"; }
  function qcBox(it) {
    var q = it.qc || { ready: false, short: {}, extra: {}, block_reason: "不能放行" };
    return '<div class="qc' + (q.ready ? " ready" : "") + '"><b>QC</b> 短片 ' + esc(qcName(q.short && q.short.state)) + "／加驗 " + esc(qcName(q.extra && q.extra.state)) + "。" + (q.ready ? "兩項都過，仍要另有發佈核准才算可發。" : esc(q.block_reason || "不能放行")) + "</div>";
  }
  function spokenText(it) {
    return (it.sentences || []).map(function (s) { return (s.lines || []).join("\n"); }).filter(Boolean).join("\n");
  }
  function sentences(it) {
    if (!it.sentences || !it.sentences.length) return "";
    return '<table class="sent"><thead><tr><th>時間（暫排）</th><th>中文（審稿用）</th><th>英文</th><th>備註（不是字幕）</th></tr></thead><tbody>' +
      it.sentences.map(function (s) {
        var badge = (s.en_status === "provisional" || s.en_status === "blank_pending" || s.en_status === "blanked_unsupported") ? '<div class="note">這句未定，英文不可當字幕</div>' : "";
        return '<tr class="' + esc(s.en_status) + '"><td>' + esc(s.start) + "–" + esc(s.end) + '</td><td data-spoken="1">' +
          (s.lines || []).map(esc).join("<br>") + '</td><td data-en-status="' + esc(s.en_status) + '">' + badge + esc(s.en_display) +
          '</td><td class="note" data-note="1">' + esc(s.note || "") + "</td></tr>";
      }).join("") + "</tbody></table>";
  }
  function audios(list) {
    return (list || []).map(function (u) {
      var a = u.review_audio;
      if (!a) return "";
      return '<div class="aud"><b>' + esc(u.title) + "</b><p>" + esc(u.detail) + "</p><p>" + esc(a.note) + "</p>" +
        '<iframe src="' + esc(a.embed) + '" title="' + esc(a.title) + '" allowfullscreen></iframe>' +
        '<div><a href="' + esc(a.watch) + '" target="_blank" rel="noopener">在 YouTube 從 ' + esc(a.start) + " 秒播放到 " + esc(a.end) + " 秒</a></div></div>";
    }).join("");
  }
  function media(it) {
    var m = it.media || {};
    var h = "";
    if (it.still) h += '<img class="still" alt="" src="' + it.still + '">';
    if (m.video) h += '<div><a href="' + esc(m.video) + '" target="_blank" rel="noopener">' + esc(m.video_label || "預覽") + "</a></div>";
    else if (m.missing) h += '<p class="miss">' + esc(m.missing) + "</p>";
    if (m.doc) h += '<div><a href="' + esc(m.doc) + '" target="_blank" rel="noopener">文案</a></div>';
    if (m.subs && m.subs.length) h += "<details><summary>字幕 " + m.subs.length + " 行</summary><div>" + m.subs.map(function (s) { return '<div data-spoken="1">' + esc(s) + "</div>"; }).join("") + "</div></details>";
    else if (it.kind === "cut") h += '<p class="miss">沒有字幕可顯示，不補假字幕。</p>';
    if (m.copy) h += "<details><summary>既有說明文字（不是新的發佈動作）</summary><pre class=\"excerpt\">" + esc(m.copy) + "</pre></details>";
    return h;
  }
  function show(it, ep, q) {
    if (ep && it.ep !== ep) return false;
    if (!q) return true;
    var blob = [it.title, it.ep, it.id, it.speaker, it.episode_title].join(" ").toLowerCase();
    return blob.indexOf(q) >= 0;
  }
  function card(it) {
    var d = drafts();
    var h = '<article class="card" data-id="' + esc(it.id) + '" data-artifact="' + esc(it.artifact && it.artifact.id) + '" data-section="' + esc(it.section) + '">';
    h += "<h2>" + esc(it.ep || "") + "｜" + esc(it.title || it.id) + "</h2>";
    h += '<p class="meta">' + esc(it.speaker || "") + (it.range ? " · " + esc(it.range) : "") + (it.duration ? " · " + esc(it.duration) + " 秒" : "") + "</p>";
    if (it.draft_banner) h += '<div class="banner">' + esc(it.draft_banner) + "</div>";
    if (it.selection_note) h += '<p class="note">' + esc(it.selection_note) + "</p>";
    h += flags(it);
    h += platforms(it);
    h += qcBox(it);
    if (it.hold) h += '<div class="banner">暫停：' + esc(it.hold.label || "") + " " + esc(it.hold.reason || "") + "</div>";
    if (it.historical) h += '<p class="note">歷史信件：' + esc(it.historical.decision) + "（" + esc(it.historical.at || "") + "）。" + esc(it.historical.note) + "</p>";
    (it.related_notes || []).forEach(function (n) { h += '<p class="note">' + esc(n) + "</p>"; });
    if (it.cut_file_note) h += '<p class="note">' + esc(it.cut_file_note) + "</p>";
    if (it.schedule_label) h += '<p class="meta">舊排程標籤（唯讀，這次沒改）：' + esc(it.schedule_label) + "</p>";
    h += '<p class="meta">身份 ' + esc(it.artifact && it.artifact.id) + (it.artifact && it.artifact.mtime_taipei ? " · 檔案時間 " + esc(it.artifact.mtime_taipei) + " 台北" : "") + "</p>";
    h += media(it);
    if (it.kind === "proposal" && it.excerpt) h += '<p class="excerpt" data-excerpt="1"><b>提案摘錄，不是逐句腳本。</b> ' + esc(it.excerpt) + "</p>";
    if (it.why) h += '<p class="meta">提案理由：' + esc(it.why) + "</p>";
    if (it.episode_note) h += '<p class="meta">' + esc(it.episode_note) + "</p>";
    h += audios(it.uncertainties);
    h += sentences(it);
    if (it.recon_reason_label) h += "<p>" + esc(it.recon_reason_label) + "。不是成片卡，不能放行。</p>";
    if (it.section === "new") {
      var on = draftApplies(it.artifact && it.artifact.id, d[it.id] && d[it.id].artifact);
      h += '<label><input type="checkbox" data-pick="' + esc(it.id) + '"' + (on ? " checked" : "") + "> 暫記選片（只存在這台瀏覽器，不是核准）</label>";
    }
    if (it.section === "script") {
      var note = (d[it.id] && draftApplies(it.artifact.id, d[it.id].artifact) && d[it.id].note) || "";
      h += '<label>審稿意見（草稿）<textarea data-note-for="' + esc(it.id) + '" rows="2">' + esc(note) + "</textarea></label>";
      if (it.script_complete) h += '<div class="rowbtns"><button type="button" class="act" data-copy-spoken="' + esc(it.id) + '">複製中文逐句（不含備註、不含英文）</button></div>';
    }
    if (it.section === "cut" || it.section === "published") {
      var blocked = !(it.qc && it.qc.ready);
      h += '<div class="rowbtns"><button type="button" class="block" data-publish="' + esc(it.id) + '"' + (blocked ? " disabled" : "") + ">標記可發佈</button></div>";
      if (blocked) h += '<p class="miss">放行鈕已停用。QC 沒過之前，不能把這支標成可發。</p>';
    }
    h += "</article>";
    return h;
  }
  function render() {
    var q = document.getElementById("q").value.trim().toLowerCase();
    var sel = document.getElementById("ep");
    var eps = [];
    pool(TAB).forEach(function (it) { if (it.ep && eps.indexOf(it.ep) < 0) eps.push(it.ep); });
    eps.sort();
    var want = sel.value || sel.dataset.want || "";
    sel.innerHTML = '<option value="">所有集數</option>' + eps.map(function (e) { return "<option>" + esc(e) + "</option>"; }).join("");
    sel.value = eps.indexOf(want) >= 0 ? want : "";
    var ep = sel.value;
    var list = pool(TAB).filter(function (it) { return show(it, ep, q); });
    var intros = {
      new: "預設只看還沒選的新提案。勾選只會留在這台瀏覽器，不會變成選片核准。",
      script: "這裡是已選、但腳本還在審的項目。Cake C1–C5 是完整雙語初稿，不是已審核。",
      approved: "已核准的腳本才會在這裡。選片和初稿不會進來。",
      cut: "已剪、還沒在所有平台發完的成片。可以預覽；QC 沒過不能放行。已發的平台照樣標出來，沒發的平台不會被藏起來。",
      published: "已發佈平台的封存。預設不在第一個分頁。還有平台沒發的，仍留在成片待審。",
      recon: "沒核對成獨立成片的檔案。不是可發卡片。"
    };
    document.getElementById("list").innerHTML = '<p class="intro">' + intros[TAB] + "</p>" + (list.map(card).join("") || '<p class="miss">這一頁沒有符合的項目。</p>');
    document.querySelectorAll(".tabs button").forEach(function (b) {
      var n = pool(b.dataset.tab).length;
      b.classList.toggle("on", b.dataset.tab === TAB);
      b.textContent = b.dataset.label + "（" + n + "）";
    });
  }
  function setTab(tab) {
    TAB = tab || "new";
    if (location.hash.replace("#", "") !== TAB) history.replaceState(null, "", "#" + TAB);
    render();
  }
  function selectionLines() {
    var d = drafts();
    var lines = [];
    DATA.items.forEach(function (it) {
      if (it.section !== "new") return;
      var row = d[it.id];
      if (!row || !row.on || !draftApplies(it.artifact.id, row.artifact)) return;
      lines.push(it.id + " | " + it.title + " | proposal_selected_draft=true | script_approved=false | cut_authorized=false | publish_approved=false | artifact=" + it.artifact.id);
    });
    return lines;
  }
  function scriptLines() {
    var d = drafts();
    return DATA.items.filter(function (it) { return it.section === "script"; }).map(function (it) {
      var note = (d[it.id] && draftApplies(it.artifact.id, d[it.id].artifact) && d[it.id].note) || "";
      return it.id + " | " + it.title + " | script_review_status=pending | script_approved=false | cut_authorized=false | publish_approved=false | artifact=" + it.artifact.id + (note ? " | 意見=" + note : "");
    });
  }
  function mail(kind, lines, subject) {
    return {
      subject: subject,
      body: "狀態：草稿，尚未寄出，不是核准。\nrevision: " + DATA.revision + "\n" + lines.join("\n")
    };
  }
  function openMail(m) {
    var u = "mailto:" + DATA.to + "?subject=" + encodeURIComponent(m.subject) + "&body=" + encodeURIComponent(m.body);
    location.href = u;
    document.getElementById("msg").textContent = "已嘗試打開郵件程式。這不代表信已寄出，也不代表項目已核准，公開網站也還沒因此更新。";
  }
  function copyText(t, ok) {
    function done() { document.getElementById("msg").textContent = ok; }
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(t).then(done, done);
    else done();
  }
  document.getElementById("tabs").addEventListener("click", function (e) {
    var b = e.target.closest("button[data-tab]");
    if (b) setTab(b.dataset.tab);
  });
  document.getElementById("ep").onchange = render;
  document.getElementById("q").oninput = render;
  document.getElementById("list").addEventListener("change", function (e) {
    var box = e.target.closest("input[data-pick]");
    if (box) {
      var it = DATA.items.filter(function (x) { return x.id === box.dataset.pick; })[0];
      var d = drafts();
      d[it.id] = { on: box.checked, artifact: it.artifact.id };
      saveDrafts(d);
      document.getElementById("msg").textContent = "已暫記在這台瀏覽器。還沒寄出，也還沒核准。";
      return;
    }
    var area = e.target.closest("textarea[data-note-for]");
    if (area) {
      var it2 = DATA.items.filter(function (x) { return x.id === area.dataset.noteFor; })[0];
      var d2 = drafts();
      d2[it2.id] = { note: area.value, artifact: it2.artifact.id };
      saveDrafts(d2);
    }
  });
  document.getElementById("list").addEventListener("click", function (e) {
    var pub = e.target.closest("button[data-publish]");
    if (pub) {
      var it = DATA.items.filter(function (x) { return x.id === pub.dataset.publish; })[0];
      if (!it || !it.qc || !it.qc.ready) {
        document.getElementById("msg").textContent = "不能放行。QC 未過，這次點擊沒有寫成發佈核准。";
        return;
      }
    }
    var cp = e.target.closest("button[data-copy-spoken]");
    if (cp) {
      var it3 = DATA.items.filter(function (x) { return x.id === cp.dataset.copySpoken; })[0];
      copyText(spokenText(it3), "已複製中文逐句。不含備註與英文，也不是核准。");
    }
  });
  document.getElementById("actions").addEventListener("click", function (e) {
    var b = e.target.closest("button");
    if (!b) return;
    if (b.id === "copy-pick" || b.id === "mail-pick") {
      var lines = selectionLines();
      var m = mail("pick", lines, "選片 " + taipeiDate());
      if (!lines.length) { document.getElementById("msg").textContent = "還沒有勾選新提案。"; return; }
      if (b.id === "copy-pick") copyText(m.subject + "\n" + m.body, "已複製選片草稿。尚未寄出，網站狀態未改。");
      else openMail(m);
    }
    if (b.id === "copy-script" || b.id === "mail-script") {
      var m2 = mail("script", scriptLines(), "腳本意見 " + taipeiDate());
      if (b.id === "copy-script") copyText(m2.subject + "\n" + m2.body, "已複製腳本意見草稿。尚未寄出，沒有任何腳本被標成核准。");
      else openMail(m2);
    }
  });
  var params = new URLSearchParams(location.search);
  if (params.get("q")) document.getElementById("q").value = params.get("q");
  if (params.get("ep")) document.getElementById("ep").dataset.want = params.get("ep");
  var start = (location.hash || "#new").replace("#", "");
  if (["new", "script", "approved", "cut", "published", "recon"].indexOf(start) < 0) start = "new";
  var sync = document.getElementById("sync");
  sync.textContent = "修訂 " + DATA.revision.slice(0, 12) + "。公開網址若不是這個修訂，代表網站還沒更新。郵件與瀏覽器草稿都不是核准。";
  if (ignored.length) sync.textContent += " 已忽略瀏覽器舊綠燈：" + ignored.join("、") + "。";
  setTab(start);
  document.documentElement.dataset.ready = "1";
  window.__review = {
    revision: DATA.revision,
    tab: function () { return TAB; },
    setTab: setTab,
    draftApplies: draftApplies,
    spokenText: spokenText,
    qcBlocks: function (id) {
      var it = DATA.items.filter(function (x) { return x.id === id; })[0];
      return !it || !it.qc || !it.qc.ready;
    },
    poolSize: function (tab) { return pool(tab).length; },
    ignoredLegacy: ignored
  };
})();
