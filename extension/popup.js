/* ApplyJin Chrome Extension — Popup script */

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

/* ---------- tabs ---------- */

$$(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    $$(".tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    $$(".section").forEach((s) => s.classList.add("hidden"));
    $(`#tab-${tab.dataset.tab}`).classList.remove("hidden");
  });
});

/* ---------- settings ---------- */

let API_URL = "";
let AUTH_TOKEN = "";

chrome.storage.local.get(["apiUrl", "authToken"], (data) => {
  if (data.apiUrl) {
    API_URL = data.apiUrl;
    $("#input-url").value = data.apiUrl;
  }
  if (data.authToken) {
    AUTH_TOKEN = data.authToken;
    $("#input-token").value = data.authToken;
  }
  checkConnection();
});

$("#btn-save-settings").addEventListener("click", () => {
  API_URL = $("#input-url").value.replace(/\/+$/, "");
  AUTH_TOKEN = $("#input-token").value;
  chrome.storage.local.set({ apiUrl: API_URL, authToken: AUTH_TOKEN }, () => {
    $("#settings-saved").classList.remove("hidden");
    setTimeout(() => $("#settings-saved").classList.add("hidden"), 2000);
    checkConnection();
  });
});

/* ---------- connection check ---------- */

async function checkConnection() {
  const dot = $("#status-dot");
  if (!API_URL) {
    dot.classList.add("offline");
    dot.title = "No backend URL configured";
    return;
  }
  try {
    const resp = await fetch(`${API_URL}/api/health`);
    if (resp.ok) {
      dot.classList.remove("offline");
      dot.title = "Connected to ApplyJin backend";
    } else {
      dot.classList.add("offline");
      dot.title = "Backend returned error";
    }
  } catch {
    dot.classList.add("offline");
    dot.title = "Cannot reach backend";
  }
}

/* ---------- page scanning ---------- */

let detectedFields = [];
let pageTitle = "";
let pageCompany = "";

chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
  if (!tabs[0]) return;
  chrome.tabs.sendMessage(tabs[0].id, { action: "scan" }, (response) => {
    if (chrome.runtime.lastError || !response) {
      $("#page-info").textContent = "No application form detected on this page.";
      return;
    }
    pageTitle = response.title || "";
    pageCompany = response.company || "";
    detectedFields = response.fields || [];

    if (detectedFields.length === 0) {
      $("#page-info").textContent = "Page detected but no fillable form fields found.";
      return;
    }

    $("#page-info").innerHTML = `
      <div style="font-weight: 500; margin-bottom: 4px">${pageTitle || "Unknown role"}</div>
      <div style="color: rgba(225,224,204,0.5); font-size: 11px">${pageCompany || "Unknown company"} · ${detectedFields.length} fields detected</div>
    `;
    $("#autofill-form").classList.remove("hidden");
    renderFields(detectedFields);
  });
});

function renderFields(fields) {
  const container = $("#fields-list");
  container.innerHTML = "";
  fields.forEach((f, i) => {
    const div = document.createElement("div");
    div.className = "field-item";
    div.innerHTML = `
      <div>
        <span style="color: rgba(225,224,204,0.6)">${f.label || f.name || f.type}</span>
        <span class="${f.detectable ? 'detected' : 'missing'}" style="margin-left: 6px; font-size: 10px">
          ${f.detectable ? '● detected' : '○ unknown'}
        </span>
      </div>
      <button class="btn-secondary" data-idx="${i}" style="width: auto; padding: 4px 10px; font-size: 11px; border-radius: 6px; margin: 0">
        ${f.value ? 'filled' : 'fill'}
      </button>
    `;
    container.appendChild(div);
  });
}

/* ---------- autofill ---------- */

async function getResumeData() {
  // Try to get from backend
  if (!API_URL) return null;
  try {
    const headers = { "Content-Type": "application/json" };
    if (AUTH_TOKEN) headers["Authorization"] = `Bearer ${AUTH_TOKEN}`;
    const resp = await fetch(`${API_URL}/api/resumes`, { headers });
    if (!resp.ok) return null;
    const resumes = await resp.json();
    // Get the latest resume's structured data
    if (resumes.length > 0) {
      const latest = resumes[0];
      return {
        firstName: latest.first_name || "",
        lastName: latest.last_name || "",
        email: latest.email || "",
        phone: latest.phone || "",
        linkedin: latest.linkedin || "",
        github: latest.github || "",
        portfolio: latest.portfolio || "",
        summary: latest.summary || "",
        location: latest.location || "",
      };
    }
  } catch {}
  return null;
}

function mapField(field, data) {
  const name = (field.name || "").toLowerCase();
  const label = (field.label || "").toLowerCase();
  const combined = name + " " + label;

  if (combined.match(/first.*name|fname/)) return data.firstName;
  if (combined.match(/last.*name|lname|surname/)) return data.lastName;
  if (combined.match(/full.*name|name/) && !combined.match(/first|last|company/)) return `${data.firstName} ${data.lastName}`.trim();
  if (combined.match(/email/)) return data.email;
  if (combined.match(/phone|tel|mobile/)) return data.phone;
  if (combined.match(/linkedin/)) return data.linkedin;
  if (combined.match(/github/)) return data.github;
  if (combined.match(/portfolio|website|url|blog/)) return data.portfolio;
  if (combined.match(/location|city|address|zip/)) return data.location;
  if (combined.match(/summary|about|bio|objective/)) return data.summary;
  return null;
}

async function fillFields(selectedOnly = false) {
  const data = await getResumeData();
  if (!data) {
    alert("No resume data found. Make sure you have uploaded a resume to ApplyJin and configured the backend URL in Settings.");
    return;
  }

  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (!tabs[0]) return;

    const fillMap = {};
    detectedFields.forEach((f, i) => {
      if (selectedOnly && !f.selected) return;
      const value = mapField(f, data);
      if (value) fillMap[f.selector || `[data-field-idx="${i}"]`] = value;
    });

    chrome.tabs.sendMessage(tabs[0].id, {
      action: "fill",
      fields: fillMap,
    }, (response) => {
      if (response && response.filled) {
        const count = Object.keys(fillMap).length;
        alert(`Filled ${count} field${count !== 1 ? 's' : ''}`);
      }
    });
  });
}

$("#btn-fill").addEventListener("click", () => fillFields(false));
$("#btn-fill-selected").addEventListener("click", () => fillFields(true));

/* ---------- JD extraction ---------- */

$("#btn-extract").addEventListener("click", () => {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (!tabs[0]) return;
    chrome.tabs.sendMessage(tabs[0].id, { action: "extractJD" }, (response) => {
      if (chrome.runtime.lastError || !response || !response.jd) {
        alert("Could not extract a job description from this page.");
        return;
      }
      $("#extracted-title").textContent = response.title || "Unknown";
      $("#extracted-company").textContent = response.company || "Unknown";
      $("#extracted-length").textContent = `${response.jd.length} characters`;
      $("#extract-result").classList.remove("hidden");
    });
  });
});

$("#btn-score-jd").addEventListener("click", async () => {
  if (!API_URL) {
    alert("Configure your backend URL in Settings first.");
    return;
  }

  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (!tabs[0]) return;
    chrome.tabs.sendMessage(tabs[0].id, { action: "extractJD" }, async (response) => {
      if (!response || !response.jd) return;

      try {
        const headers = { "Content-Type": "application/json" };
        if (AUTH_TOKEN) headers["Authorization"] = `Bearer ${AUTH_TOKEN}`;

        // Create JD on backend
        const createResp = await fetch(`${API_URL}/api/jds`, {
          method: "POST",
          headers,
          body: JSON.stringify({
            title: response.title || "Untitled",
            company: response.company || "Unknown",
            description: response.jd,
            url: response.url || "",
          }),
        });

        if (!createResp.ok) throw new Error("Failed to create JD");
        const jd = await createResp.json();

        // Get ghost score
        const scoreDiv = $("#jd-score");
        scoreDiv.classList.remove("hidden");
        scoreDiv.innerHTML = `<div class="result"><div class="score">${jd.ghost_score ?? '—'}</div><div class="label">Ghost-job score (higher = more genuine)</div></div>`;
      } catch (e) {
        alert(`Error: ${e.message}`);
      }
    });
  });
});
