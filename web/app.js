const endpointList = document.getElementById("endpoint-list");
const testerForm = document.getElementById("tester-form");
const pathInput = document.getElementById("path");
const statusLabel = document.getElementById("status");
const responseView = document.getElementById("response");
const copyButton = document.getElementById("copy-response");

function setResponse(value) {
  responseView.textContent = value;
}

function setStatus(message, isError = false) {
  statusLabel.textContent = message;
  statusLabel.style.color = isError ? "#9f1239" : "#14532d";
}

async function loadApiOverview() {
  try {
    const response = await fetch("/api");
    const data = await response.json();
    const endpoints = Array.isArray(data.endpoints) ? data.endpoints : [];

    endpointList.innerHTML = "";
    endpoints.forEach((endpoint) => {
      const item = document.createElement("li");
      item.textContent = endpoint;
      item.addEventListener("click", () => {
        const normalized = endpoint.replace(/^GET\s+/i, "");
        pathInput.value = normalized;
      });
      endpointList.appendChild(item);
    });
  } catch (error) {
    setStatus(`Failed loading API docs: ${error.message}`, true);
  }
}

async function runRequest(path) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const response = await fetch(normalizedPath);

  let payload;
  const bodyText = await response.text();
  try {
    payload = JSON.parse(bodyText);
  } catch {
    payload = bodyText;
  }

  setResponse(typeof payload === "string" ? payload : JSON.stringify(payload, null, 2));
  setStatus(`${response.status} ${response.statusText}`,
    response.status >= 400);
}

testerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  setStatus("Loading...");

  try {
    await runRequest(pathInput.value.trim());
  } catch (error) {
    setStatus(`Request failed: ${error.message}`, true);
    setResponse(String(error));
  }
});

copyButton.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(responseView.textContent || "");
    setStatus("Response copied to clipboard");
  } catch {
    setStatus("Clipboard copy failed", true);
  }
});

loadApiOverview();
