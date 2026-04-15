const API_BASE = window.API_BASE_URL || "http://127.0.0.1:8000";

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
    throw new Error(data.detail || "Pedido falhou.");
  }

  return data;
}

copyForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearResults(copyResults);
  setStatus(copyStatus, "A gerar 5 copies...");

  const formData = new FormData(copyForm);
  const payload = {
    product_name: formData.get("product_name")?.toString().trim(),
    description: formData.get("description")?.toString().trim(),
    audience: formData.get("audience")?.toString().trim(),
  };

  try {
    const data = await postJSON("/generate-copy", payload);
    renderCopyResults(data.variations);
    setStatus(copyStatus, "5 copies geradas com sucesso.");
  } catch (error) {
    setStatus(copyStatus, error.message || "Erro ao gerar copy.", true);
  }
});

scriptForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearResults(scriptResults);
  setStatus(scriptStatus, "A gerar script de vídeo...");

  const formData = new FormData(scriptForm);
  const payload = {
    product_name: formData.get("product_name")?.toString().trim(),
    description: formData.get("description")?.toString().trim(),
    style: formData.get("style")?.toString().trim(),
  };

  try {
    const data = await postJSON("/generate-script", payload);
    renderScriptResults(data.script);
    setStatus(scriptStatus, "Script gerado com sucesso.");
  } catch (error) {
    setStatus(scriptStatus, error.message || "Erro ao gerar script.", true);
  }
});
