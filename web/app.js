// Enterprise-Hermes admin console
const $ = (id) => document.getElementById(id);
const TOKEN = "Bearer manager-demo-token";

async function jget(path) {
  const r = await fetch(path, { headers: { Authorization: TOKEN } });
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.json();
}

async function refresh() {
  try {
    const health = await jget("/health");
    const ov = await jget("/admin/overview");
    const gates = await jget("/gate/pending?org=acme");
    const runs = await jget("/orchestrate/runs?org=acme");
    const audit = await jget("/audit?org=acme");

    const orgs = Array.isArray(health.orgs) ? health.orgs : Object.values(health.orgs || {});
    $("c-orgs").textContent = Object.keys(ov.orgs || {}).length;
    $("c-enabled").textContent = orgs.filter((o) => o.enabled).length;
    $("c-runs").textContent = (runs.runs || []).length;
    $("c-pending").textContent = (gates.pending || []).length;
    $("status").textContent = "live · " + (health.llm_model || "n/a");
    $("status").classList.add("ok");

    // orgs table
    const otb = $("orgs").querySelector("tbody");
    otb.innerHTML = orgs.map((o) =>
      `<tr><td><code>${o.org}</code></td><td>${o.org}</td>
       <td>${o.enabled ? "✅" : "⛔"}</td><td>${o.tools}</td></tr>`).join("");

    // gates
    const gtb = $("gates").querySelector("tbody");
    gtb.innerHTML = (gates.pending || []).map((g) =>
      `<tr><td><code>${g.req_id || g.reqId || ""}</code></td>
       <td>${g.action}</td><td>${g.actor}</td><td>pending</td></tr>`).join("") || `<tr><td colspan="4" class="muted">no pending approvals</td></tr>`;

    // runs
    const rtb = $("runs").querySelector("tbody");
    rtb.innerHTML = (runs.runs || []).map((r) =>
      `<tr><td><code>${r.job_id}</code></td><td>${r.org}</td>
       <td>${r.status}</td><td>${String(r.task).slice(0, 60)}</td></tr>`).join("") || `<tr><td colspan="4" class="muted">no runs yet</td></tr>`;

    // audit
    $("audit").textContent = JSON.stringify((audit.records || []).slice(-40).reverse(), null, 2);
  } catch (e) {
    $("status").textContent = "error: " + e.message;
    $("status").style.background = "#3a1312";
  }
}

refresh();
setInterval(refresh, 8000);