"use strict";

// The login token lives only in this variable (never in localStorage or cookies),
// so it disappears when the page is closed or refreshed. Tokens also expire after 15 minutes.
let token = null;
let me = null;
let listBox = null;
let filters = {};

const app = document.getElementById("app");
const who = document.getElementById("who");

// Everything is built with createElement/append (never innerHTML), so text that comes
// from the server (file names, emails, audit details) is never parsed as HTML.
function el(tag, props, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (k === "class") n.className = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v);
  }
  for (const kid of kids) if (kid !== null && kid !== undefined) n.append(kid);
  return n;
}

const notice = el("div", { id: "notice", role: "status" });
document.body.insertBefore(notice, app);

function say(text, ok = true) {
  notice.textContent = text;
  notice.className = ok ? "ok" : "bad";
}

function safe(fn) {
  return async (...args) => {
    try {
      await fn(...args);
    } catch (e) {
      if (e.message !== "expired") say("Something went wrong. Please try again.", false);
    }
  };
}

async function api(path, opts = {}) {
  const headers = {};
  if (token) headers["Authorization"] = "Bearer " + token;
  let body = opts.body;
  if (opts.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.json);
  }
  const res = await fetch(path, { method: opts.method || "GET", headers, body });
  if (res.status === 401 && token) {
    logout("Your session expired. Please log in again.");
    throw new Error("expired");
  }
  return res;
}

function logout(message) {
  token = null;
  me = null;
  who.replaceChildren();
  renderLogin();
  if (message) say(message, message === "Logged out");
}

// ---------- Login ----------
function renderLogin() {
  const email = el("input", { type: "email", placeholder: "Email", autocomplete: "username" });
  const password = el("input", { type: "password", placeholder: "Password", autocomplete: "current-password" });

  const doLogin = safe(async () => {
    const res = await fetch("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email.value, password: password.value }),
    });
    if (!res.ok) return say("Wrong email or password", false);
    token = (await res.json()).access_token;
    me = await (await api("/auth/me")).json();
    say("Logged in", true);
    renderHome();
  });

  const doSignup = safe(async () => {
    const res = await fetch("/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email.value, password: password.value }),
    });
    if (!res.ok) return say("Could not create the account (password must be 8 to 64 characters)", false);
    say("Account created as a viewer. You can log in now.", true);
  });

  password.addEventListener("keydown", (e) => { if (e.key === "Enter") doLogin(); });

  app.replaceChildren(
    el("section", { class: "card" },
      el("h2", {}, "Log in"),
      email,
      password,
      el("div", { class: "row" },
        el("button", { onclick: doLogin }, "Log in"),
        el("button", { class: "secondary", onclick: doSignup }, "Create viewer account")),
      el("p", { class: "hint" }, "Demo accounts are listed in the README. New accounts are always viewers.")
    )
  );
}

// ---------- Home ----------
function renderHome() {
  who.replaceChildren(
    el("span", {}, `${me.email} (${me.role})`),
    el("button", { class: "secondary", onclick: () => logout("Logged out") }, "Log out")
  );
  if (me.role === "admin") {
    app.replaceChildren(adminCard());
    return;
  }
  const parts = [];
  if (me.role === "owner") parts.push(uploadCard());
  parts.push(documentsCard());
  app.replaceChildren(...parts);
  loadDocs();
}

// ---------- Upload (owners) ----------
function uploadCard() {
  const file = el("input", { type: "file" });
  const category = el("input", { placeholder: "Category", value: "general" });
  const go = safe(async () => {
    if (!file.files[0]) return say("Choose a file first", false);
    const fd = new FormData();
    fd.append("file", file.files[0]);
    fd.append("category", category.value || "general");
    const res = await api("/documents", { method: "POST", body: fd });
    if (res.status === 413) return say("File too large (max 5 MB)", false);
    if (!res.ok) return say("Upload refused: only pdf, png, jpg or txt files whose content matches the type", false);
    say("Uploaded", true);
    file.value = "";
    await loadDocs();
  });
  return el("section", { class: "card" },
    el("h2", {}, "Upload"),
    el("div", { class: "row wrap" }, file, category, el("button", { onclick: go }, "Upload"))
  );
}

// ---------- Documents ----------
function documentsCard() {
  const q = el("input", { placeholder: "Search by name" });
  const category = el("input", { placeholder: "Category" });
  const owner = el("input", { placeholder: "Owner email" });
  const from = el("input", { type: "date", title: "From date" });
  const to = el("input", { type: "date", title: "To date" });
  listBox = el("div", { id: "docs" });
  const go = safe(async () => {
    filters = { q: q.value, category: category.value, owner: owner.value, date_from: from.value, date_to: to.value };
    await loadDocs();
  });
  return el("section", { class: "card" },
    el("h2", {}, "Documents you can access"),
    el("div", { class: "row wrap" }, q, category, owner, from, to, el("button", { onclick: go }, "Search")),
    listBox
  );
}

const loadDocs = safe(async () => {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(filters)) if (v) params.set(k, v);
  const res = await api("/documents?" + params.toString());
  if (!res.ok) return say("Could not load documents", false);
  const docs = await res.json();
  if (!docs.length) {
    listBox.replaceChildren(el("p", { class: "hint" }, "No documents you can access."));
    return;
  }
  listBox.replaceChildren(...docs.map(docRow));
});

function docRow(d) {
  // Showing or hiding buttons is only a convenience. The server decides on every request.
  const isOwner = d.owner === me.email;
  const panel = el("div", { class: "panel" });
  const buttons = [
    el("button", { onclick: safe(() => download(d)) }, "Download"),
    el("button", { class: "secondary", onclick: safe(() => rename(d)) }, "Rename"),
  ];
  if (isOwner) {
    buttons.push(el("button", { class: "secondary", onclick: safe(() => togglePanel(d, panel)) }, "Share"));
    buttons.push(el("button", { class: "danger", onclick: safe(() => remove(d)) }, "Delete"));
  }
  return el("div", { class: "doc" },
    el("div", { class: "meta" },
      el("strong", {}, d.name),
      el("span", {}, `${d.category} · ${d.owner} · ${Math.ceil(d.size / 1024)} KB · ${String(d.created_at).slice(0, 10)}`)),
    el("div", { class: "row wrap" }, ...buttons),
    panel
  );
}

async function download(d) {
  const res = await api(`/documents/${d.id}/download`);
  if (!res.ok) return say(`Refused (${res.status}): not found or not allowed`, false);
  const url = URL.createObjectURL(await res.blob());
  const a = el("a", { href: url, download: d.name });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  say("Downloaded " + d.name, true);
}

async function rename(d) {
  const name = prompt("New name", d.name);
  if (!name) return;
  const res = await api(`/documents/${d.id}`, { method: "PUT", json: { name } });
  if (!res.ok) return say("Not allowed (renaming needs edit access)", false);
  say("Renamed", true);
  await loadDocs();
}

async function remove(d) {
  if (!confirm(`Delete "${d.name}"?`)) return;
  const res = await api(`/documents/${d.id}`, { method: "DELETE" });
  if (!res.ok) return say("Not allowed", false);
  say("Deleted", true);
  await loadDocs();
}

// ---------- Sharing (document owner) ----------
async function togglePanel(d, panel) {
  if (panel.childNodes.length) {
    panel.replaceChildren();
    return;
  }
  await refreshShares(d, panel);
}

async function refreshShares(d, panel) {
  const res = await api(`/documents/${d.id}/shares`);
  if (!res.ok) return say(`Could not load sharing (${res.status})`, false);
  const shares = await res.json();

  const email = el("input", { type: "email", placeholder: "Person's email" });
  const level = el("select", {}, el("option", { value: "read" }, "read"), el("option", { value: "edit" }, "edit"));
  const add = safe(async () => {
    const r = await api(`/documents/${d.id}/share`, { method: "POST", json: { email: email.value, level: level.value } });
    if (!r.ok) return say("Could not share (check the email address)", false);
    say("Access granted", true);
    await refreshShares(d, panel);
  });

  const rows = shares.map((s) =>
    el("div", { class: "share" },
      el("span", {}, `${s.email} (${s.level})`),
      el("button", {
        class: "danger",
        onclick: safe(async () => {
          const r = await api(`/documents/${d.id}/share/${s.user_id}`, { method: "DELETE" });
          if (!r.ok) return say("Could not take access back", false);
          say("Access taken back. It stops working immediately.", true);
          await refreshShares(d, panel);
        }),
      }, "Revoke"))
  );

  panel.replaceChildren(
    el("h4", {}, "People with access"),
    ...(rows.length ? rows : [el("p", { class: "hint" }, "Nobody else has access.")]),
    el("div", { class: "row wrap" }, email, level, el("button", { onclick: add }, "Share"))
  );
}

// ---------- Admin ----------
function adminCard() {
  const actions = ["", "upload", "download", "edit", "delete", "permission_grant", "permission_revoke", "permission_view", "role_change", "login_failed"];
  const action = el("select", {}, ...actions.map((a) => el("option", { value: a }, a || "all actions")));
  const out = el("div", { class: "scroll" });
  const verdict = el("p", { class: "hint" });

  const load = safe(async () => {
    const params = new URLSearchParams({ limit: "100" });
    if (action.value) params.set("action", action.value);
    const res = await api("/admin/audit?" + params.toString());
    if (!res.ok) return say("Could not load the audit log", false);
    const rows = await res.json();
    const head = el("tr", {}, ...["#", "time (UTC)", "actor", "action", "doc", "result", "detail"].map((h) => el("th", {}, h)));
    const body = rows.map((r) =>
      el("tr", { class: r.result === "denied" ? "denied" : "" },
        el("td", {}, r.id),
        el("td", {}, String(r.ts).replace("T", " ").slice(0, 19)),
        el("td", {}, r.actor_id ?? ""),
        el("td", {}, r.action),
        el("td", {}, r.doc_id ?? ""),
        el("td", {}, r.result),
        el("td", {}, r.detail))
    );
    out.replaceChildren(el("table", {}, el("thead", {}, head), el("tbody", {}, ...body)));
  });

  const verify = safe(async () => {
    const res = await api("/admin/audit/verify");
    if (!res.ok) return say("Could not verify the audit log", false);
    const v = await res.json();
    verdict.textContent = v.intact ? "Audit chain intact." : `Audit chain BROKEN at row ${v.first_broken_row}.`;
    verdict.className = v.intact ? "ok" : "bad";
  });

  const uid = el("input", { type: "number", min: "1", placeholder: "User id" });
  const role = el("select", {}, ...["viewer", "owner", "admin"].map((r) => el("option", { value: r }, r)));
  const setRole = safe(async () => {
    if (!uid.value) return say("Enter a user id", false);
    const res = await api(`/admin/users/${encodeURIComponent(uid.value)}/role`, { method: "PUT", json: { role: role.value } });
    if (!res.ok) return say("Could not change the role", false);
    say("Role changed. That user's old login tokens stopped working.", true);
    await load();
  });

  load();
  return el("div", { class: "card-stack" },
    el("section", { class: "card" },
      el("h2", {}, "Audit trail"),
      el("div", { class: "row wrap" },
        action,
        el("button", { onclick: load }, "Show"),
        el("button", { class: "secondary", onclick: verify }, "Verify chain")),
      verdict,
      out),
    el("section", { class: "card" },
      el("h2", {}, "Change a user's role"),
      el("div", { class: "row wrap" }, uid, role, el("button", { onclick: setRole }, "Change")),
      el("p", { class: "hint" }, "Admins see activity and manage roles. They cannot open document contents."))
  );
}

renderLogin();
