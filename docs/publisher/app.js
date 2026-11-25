/* White Hole Publisher — front end. Follows TikTok's Content Sharing Guidelines for Direct Post. */
(() => {
  const C = window.WHP;
  const $ = (id) => document.getElementById(id);
  const SID_KEY = "whp_sid";
  const MUSIC = '<a href="https://www.tiktok.com/legal/page/global/music-usage-confirmation/en" target="_blank" rel="noopener">Music Usage Confirmation</a>';
  const BCP = '<a href="https://www.tiktok.com/legal/page/global/bc-policy/en" target="_blank" rel="noopener">Branded Content Policy</a>';
  const PRIVACY_LABELS = {
    PUBLIC_TO_EVERYONE: "Everyone", MUTUAL_FOLLOW_FRIENDS: "Friends", FOLLOWER_OF_CREATOR: "Followers", SELF_ONLY: "Only me"
  };
  const store = {
    get: (k) => { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} },
    del: (k) => { try { localStorage.removeItem(k); } catch (e) {} }
  };

  let sid = store.get(SID_KEY);
  let creator = null, video = null, pollTimer = null;

  async function api(action, data = {}) {
    const r = await fetch(C.API, { method: "POST", headers: { "Content-Type": "text/plain;charset=utf-8" },
      body: JSON.stringify(Object.assign({ action, sid }, data)) });
    const d = await r.json();
    if (!d.ok) { const e = new Error(d.error || "error"); e.code = d.error; throw e; }
    return d;
  }

  function status(kind, html) { const s = $("status"); s.className = "status show " + kind; s.innerHTML = html; }
  function clearStatus() { $("status").className = "status"; }

  /* ---------- connect / disconnect ---------- */
  function showConnect() { $("vConnect").hidden = false; $("vApp").hidden = true; }
  $("btnConnect").onclick = () => {
    const state = crypto.getRandomValues(new Uint32Array(4)).join("");
    try { sessionStorage.setItem("whp_state", state); } catch (e) {}
    const u = new URL("https://www.tiktok.com/v2/auth/authorize/");
    u.searchParams.set("client_key", C.CLIENT_KEY);
    u.searchParams.set("scope", C.SCOPES);
    u.searchParams.set("response_type", "code");
    u.searchParams.set("redirect_uri", C.REDIRECT);
    u.searchParams.set("state", state);
    location.href = u.toString();
  };
  $("btnDisconnect").onclick = async (e) => {
    e.preventDefault();
    if (!confirm("Disconnect your TikTok account from White Hole Publisher?")) return;
    try { await api("disconnect"); } catch (err) {}
    store.del(SID_KEY); sid = null; showConnect();
  };

  /* ---------- creator info ---------- */
  async function loadCreator() {
    try {
      creator = (await api("creator")).creator;
    } catch (err) {
      if (/not_connected|reconnect_required|access_token_invalid|scope_not_authorized/.test(err.code || "")) { store.del(SID_KEY); sid = null; showConnect(); return false; }
      $("vConnect").hidden = true; $("vApp").hidden = false;
      status("bad", friendly(err.code)); return false;
    }
    $("vConnect").hidden = true; $("vApp").hidden = false;
    $("cAvatar").src = creator.creator_avatar_url || "../logo.png";
    $("cName").textContent = creator.creator_nickname || "TikTok creator";
    $("cSub").textContent = creator.creator_username ? "@" + creator.creator_username : "TikTok account";
    const sel = $("privacy");
    sel.innerHTML = '<option value="" selected disabled>Select privacy level</option>';
    (creator.privacy_level_options || []).forEach((v) => {
      const o = document.createElement("option"); o.value = v; o.textContent = PRIVACY_LABELS[v] || v; sel.appendChild(o);
    });
    setDisabled("lComment", "allowComment", creator.comment_disabled, "Comments are turned off in your TikTok settings.");
    setDisabled("lDuet", "allowDuet", creator.duet_disabled, "Duet is turned off in your TikTok settings.");
    setDisabled("lStitch", "allowStitch", creator.stitch_disabled, "Stitch is turned off in your TikTok settings.");
    refresh();
    return true;
  }
  function setDisabled(labelId, inputId, off, why) {
    const l = $(labelId), i = $(inputId);
    i.checked = false; i.disabled = !!off; l.classList.toggle("disabled", !!off); l.title = off ? why : "";
  }

  function friendly(code) {
    const m = {
      spam_risk_too_many_posts: "You have reached the daily posting limit for your TikTok account. Please try again tomorrow.",
      spam_risk_user_banned_from_posting: "TikTok is not allowing this account to post right now.",
      reached_active_user_cap: "White Hole Publisher has reached today's limit of creators. Please try again later.",
      unaudited_client_can_only_post_to_private_accounts: "This app can only post to private accounts until it is approved by TikTok.",
      privacy_required: "Please choose who can view this video.",
      consent_required: "Please confirm before posting.",
      branded_content_cannot_be_private: "Branded content visibility cannot be set to private.",
      schedule_must_be_in_future: "Please pick a time at least a few minutes in the future."
    };
    return m[code] || ("Something went wrong (" + (code || "unknown") + "). Please try again.");
  }

  /* ---------- library & upload ---------- */
  document.querySelectorAll(".tabs button").forEach((b) => b.onclick = () => {
    document.querySelectorAll(".tabs button").forEach((x) => x.classList.remove("on")); b.classList.add("on");
    $("tLib").hidden = b.dataset.t !== "lib"; $("tUp").hidden = b.dataset.t !== "up";
  });
  async function loadLibrary() {
    const box = $("tLib");
    try {
      const lib = await (await fetch(C.LIBRARY + "?t=" + Date.now())).json();
      box.innerHTML = "";
      if (!lib.length) { box.innerHTML = '<div class="empty">Your library is empty.</div>'; return; }
      lib.forEach((it) => {
        const d = document.createElement("div"); d.className = "item";
        d.innerHTML = `<video src="${it.url}#t=1.5" preload="metadata" muted playsinline></video><span></span>`;
        d.querySelector("span").textContent = it.title;
        d.onclick = () => {
          document.querySelectorAll(".item").forEach((x) => x.classList.remove("on")); d.classList.add("on");
          pick({ kind: "library", url: it.url, caption: it.caption || it.title });
        };
        box.appendChild(d);
      });
    } catch (e) { box.innerHTML = '<div class="empty">Could not load your library.</div>'; }
  }
  $("file").onchange = (e) => {
    const f = e.target.files[0]; if (!f) return;
    document.querySelectorAll(".item").forEach((x) => x.classList.remove("on"));
    pick({ kind: "upload", file: f, url: URL.createObjectURL(f), caption: "" });
  };
  function pick(v) {
    video = Object.assign({ duration: 0 }, v);
    const p = $("preview"); p.innerHTML = "";
    const el = document.createElement("video");
    el.src = v.url; el.controls = true; el.playsInline = true; el.preload = "metadata";
    el.onloadedmetadata = () => { video.duration = el.duration; refresh(); };
    p.appendChild(el);
    $("title").value = v.caption; updateCount();
    const later = document.querySelector('input[name=when][value=later]');
    later.disabled = v.kind === "upload";
    later.parentElement.title = v.kind === "upload" ? "Scheduling is available for videos in your library." : "";
    if (v.kind === "upload") document.querySelector('input[name=when][value=now]').checked = true;
    whenChanged(); clearStatus(); refresh();
  }

  /* ---------- form logic ---------- */
  function updateCount() { $("titleCount").textContent = $("title").value.length; }
  $("title").oninput = updateCount;
  function whenMode() { return document.querySelector("input[name=when]:checked").value; }
  function whenChanged() {
    const later = whenMode() === "later"; $("whenAt").hidden = !later;
    const draft = whenMode() === "draft";
    ["fPrivacy"].forEach((id) => $(id).style.opacity = draft ? .45 : 1);
    $("privacy").disabled = draft;
    if (later && !$("whenAt").value) {
      const d = new Date(Date.now() + 60 * 60 * 1000); d.setMinutes(0, 0, 0);
      $("whenAt").value = new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
    }
    refresh();
  }
  document.querySelectorAll("input[name=when]").forEach((r) => r.onchange = whenChanged);
  ["privacy", "commercial", "yourBrand", "branded", "whenAt"].forEach((id) => $(id).addEventListener("change", refresh));

  function refresh() {
    const commercial = $("commercial").checked, yours = $("yourBrand").checked, branded = $("branded").checked;
    $("commercialBox").hidden = !commercial;
    if (!commercial) { $("yourBrand").checked = false; $("branded").checked = false; }

    // Branded content can't be private: disable "Only me" while it is selected, and vice versa.
    const sel = $("privacy");
    [...sel.options].forEach((o) => {
      if (o.value === "SELF_ONLY") {
        o.disabled = commercial && branded;
        o.title = o.disabled ? "Branded content visibility cannot be set to private." : "";
        o.textContent = o.disabled ? "Only me (not available for branded content)" : PRIVACY_LABELS.SELF_ONLY;
      }
    });
    if (commercial && branded && sel.value === "SELF_ONLY") sel.value = "";
    const priv = sel.value === "SELF_ONLY";
    $("branded").disabled = priv;
    $("lBranded").classList.toggle("disabled", priv);
    $("lBranded").dataset.tip = priv ? "Branded content visibility cannot be set to private." : "";
    if (priv) $("branded").checked = false;

    const b2 = $("branded").checked, y2 = $("yourBrand").checked;
    $("labelInfo").textContent = !commercial ? "" :
      b2 ? "Your photo/video will be labeled as 'Paid partnership'" :
      y2 ? "Your photo/video will be labeled as 'Promotional content'" : "";

    $("consent").innerHTML = commercial && b2
      ? `By posting, you agree to TikTok's ${BCP} and ${MUSIC}.`
      : `By posting, you agree to TikTok's ${MUSIC}.`;

    // Publish button state
    let why = "";
    if (!video) why = "Choose a video first.";
    else if (creator && creator.max_video_post_duration_sec && video.duration > creator.max_video_post_duration_sec)
      why = `This video is longer than the ${creator.max_video_post_duration_sec}-second limit for your account.`;
    else if (whenMode() === "draft" && video.kind !== "library") why = "Drafts can be sent for videos in your library.";
    else if (!sel.value && whenMode() !== "draft") why = "Choose who can view this video.";
    else if (commercial && !b2 && !y2) why = "You need to indicate if your content promotes yourself, a third party, or both.";
    else if (whenMode() === "later" && !$("whenAt").value) why = "Pick a date and time.";
    $("btnPost").disabled = !!why;
    $("postTip").dataset.tip = why;
    $("btnPost").textContent = { later: "Schedule", draft: "Send to TikTok" }[whenMode()] || "Post";
  }

  /* ---------- posting ---------- */
  $("form").onsubmit = async (e) => {
    e.preventDefault(); if ($("btnPost").disabled) return;
    const body = {
      title: $("title").value, privacy_level: $("privacy").value,
      allow_comment: $("allowComment").checked, allow_duet: $("allowDuet").checked, allow_stitch: $("allowStitch").checked,
      brand_organic_toggle: $("commercial").checked && $("yourBrand").checked,
      brand_content_toggle: $("commercial").checked && $("branded").checked,
      consent: true
    };
    $("btnPost").disabled = true;
    try {
      if (video.kind === "library" && whenMode() === "draft") {
        status("info", "Sending the video to your TikTok inbox…");
        const d = await api("draft", { video_url: video.url, consent: true });
        status("ok", "Sent! Open TikTok and tap the notification in your inbox to edit and post it.");
        track(d.publish_id, true);
      } else if (video.kind === "library" && whenMode() === "later") {
        const at = new Date($("whenAt").value);
        await api("post", Object.assign(body, { video_url: video.url, schedule_at: at.toISOString() }));
        status("ok", `Scheduled for <b>${at.toLocaleString()}</b>. White Hole Publisher will post it to your TikTok account at that time.`);
        loadQueue();
      } else if (video.kind === "library") {
        status("info", "Sending your video to TikTok…");
        const d = await api("post", Object.assign(body, { video_url: video.url }));
        track(d.publish_id);
      } else {
        status("info", "Uploading your video to TikTok…");
        const d = await api("upload_init", Object.assign(body, { video_size: video.file.size }));
        const up = await fetch(d.upload_url, { method: "PUT", body: video.file,
          headers: { "Content-Type": video.file.type || "video/mp4", "Content-Range": `bytes 0-${video.file.size - 1}/${video.file.size}` } });
        if (!up.ok) throw Object.assign(new Error("upload_failed"), { code: "upload_failed" });
        track(d.publish_id);
      }
    } catch (err) { status("bad", friendly(err.code)); }
    refresh();
  };

  function track(publishId, quiet) {
    clearInterval(pollTimer);
    const names = {
      PROCESSING_UPLOAD: "TikTok is receiving your video…", PROCESSING_DOWNLOAD: "TikTok is downloading your video…",
      SEND_TO_USER_INBOX: "Sent to your TikTok inbox.", PUBLISH_COMPLETE: "Posted! Your video is on your TikTok profile.",
      FAILED: "TikTok could not post this video."
    };
    let n = 0;
    if (!quiet) status("info", "Posted to TikTok. Processing can take a few minutes before it appears on your profile…");
    pollTimer = setInterval(async () => {
      n++;
      try {
        const s = (await api("status", { publish_id: publishId })).status;
        const st = s.status || "PROCESSING_UPLOAD";
        if (st === "SEND_TO_USER_INBOX") { clearInterval(pollTimer); status("ok", "✅ Sent to your TikTok inbox. Open TikTok and tap the notification to finish posting."); }
        else if (st === "PUBLISH_COMPLETE") { clearInterval(pollTimer); status("ok", "✅ " + names[st]); }
        else if (st === "FAILED") { clearInterval(pollTimer); status("bad", names[st] + (s.fail_reason ? " Reason: " + s.fail_reason : "")); }
        else status("info", (names[st] || "Processing…") + " This can take a few minutes.");
      } catch (err) { /* keep polling */ }
      if (n > 60) { clearInterval(pollTimer); status("info", "TikTok is still processing your video. It will appear on your profile when it's ready."); }
    }, 5000);
  }

  async function loadQueue() {
    const box = $("queue");
    try {
      const q = (await api("queue")).queue.sort((a, b) => a.when - b.when);
      if (!q.length) { box.innerHTML = '<div class="empty">Nothing scheduled.</div>'; return; }
      box.innerHTML = "";
      q.forEach((it) => {
        const r = document.createElement("div"); r.className = "qrow";
        const label = { scheduled: "Scheduled", sent: "Sent", failed: "Failed" }[it.state] || it.state;
        r.innerHTML = `<div><div class="t"></div><div class="muted">${new Date(it.when).toLocaleString()} · ${label}</div></div>`;
        r.querySelector(".t").textContent = (it.info.title || "Untitled").slice(0, 46);
        if (it.state === "scheduled") {
          const b = document.createElement("a"); b.href = "#"; b.textContent = "Cancel";
          b.onclick = async (e) => { e.preventDefault(); await api("cancel", { id: it.id }); loadQueue(); };
          r.appendChild(b);
        }
        box.appendChild(r);
      });
    } catch (e) { box.innerHTML = '<div class="empty">Could not load scheduled posts.</div>'; }
  }

  /* ---------- start ---------- */
  (async () => {
    if (!sid) { showConnect(); return; }
    if (await loadCreator()) { loadLibrary(); loadQueue(); }
  })();
})();
