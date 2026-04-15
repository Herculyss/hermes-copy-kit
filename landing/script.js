const API_BASE = window.API_BASE_URL || "http://127.0.0.1:8000";
const GUMROAD_URL = "https://fuioherm.gumroad.com/l/copysnap";

const copyForm = document.getElementById("copyGeneratorForm");
const scriptForm = document.getElementById("scriptGeneratorForm");
const copyStatus = document.getElementById("copyStatus");
const scriptStatus = document.getElementById("scriptStatus");
const copyResults = document.getElementById("copyResults");
const scriptResults = document.getElementById("scriptResults");

function setStatus(element, message, isError = false) {
  element.textContent = message;
  element.classList.toggle("error", isError);
}

function clearResults(element) {
  element.innerHTML = "";
}

function renderCopyResults(variations) {
  clearResults(copyResults);
  variations.forEach((variation, index) => {
    const item = document.createElement("div");
    item.className = "result-item";
    item.textContent = `${index + 1}. ${variation}`;
    copyResults.appendChild(item);
  });
}

function renderScriptResults(script) {
  clearResults(scriptResults);
  [
    ["Hook", script.hook],
    ["Problem", script.problem],
    ["Solution", script.solution],
    ["CTA", script.cta],
  ].forEach(([label, text]) => {
    const block = document.createElement("div");
    block.className = "script-block";
    block.innerHTML = `<strong>${label}</strong><span>${text}</span>`;
    scriptResults.appendChild(block);
  });
}

function renderUpgradeOffer(container, message, upgradeUrl = GUMROAD_URL) {
  clearResults(container);
  const box = document.createElement("div");
  box.className = "upgrade-card";
  box.innerHTML = `
    <p>${message}</p>
    <a class="button primary full" href="${upgradeUrl}" target="_blank" rel="noreferrer">
      Get unlimited access
    </a>
  `;
  container.appendChild(box);
}

async function postJSON(endpoint, payload) {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const error = new Error(data.error || data.detail || "Request failed.");
    error.status = response.status;
    error.payload = data;
    throw error;
  }

  return data;
}

copyForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearResults(copyResults);
  setStatus(copyStatus, "Generating 5 copy variations...");

  const formData = new FormData(copyForm);
  const payload = {
    product_name: formData.get("product_name")?.toString().trim(),
    description: formData.get("description")?.toString().trim(),
    audience: formData.get("audience")?.toString().trim(),
  };

  try {
    const data = await postJSON("/generate-copy", payload);
    renderCopyResults(data.variations);
    setStatus(copyStatus, "Your copy variations are ready.");
  } catch (error) {
    if (error.status === 429) {
      setStatus(copyStatus, error.message, true);
      renderUpgradeOffer(copyResults, error.message, error.payload?.upgrade_url || GUMROAD_URL);
      return;
    }

    setStatus(copyStatus, error.message || "Could not generate copy.", true);
  }
});

scriptForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearResults(scriptResults);
  setStatus(scriptStatus, "Generating your video script...");

  const formData = new FormData(scriptForm);
  const payload = {
    product_name: formData.get("product_name")?.toString().trim(),
    description: formData.get("description")?.toString().trim(),
    style: formData.get("style")?.toString().trim(),
  };

  try {
    const data = await postJSON("/generate-script", payload);
    renderScriptResults(data.script);
    setStatus(scriptStatus, "Your script is ready.");
  } catch (error) {
    if (error.status === 429) {
      setStatus(scriptStatus, error.message, true);
      renderUpgradeOffer(scriptResults, error.message, error.payload?.upgrade_url || GUMROAD_URL);
      return;
    }

    setStatus(scriptStatus, error.message || "Could not generate the script.", true);
  }
});
