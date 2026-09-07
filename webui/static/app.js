// UniBridge Web GUI: fetchベースの最小限フロントロジック（ADR-0004、外部CDN依存なし）

const ALLOWED_EXTENSIONS = [".usd", ".usda", ".usdc", ".usdz"];
const MAX_FILE_SIZE = 200 * 1024 * 1024;

function validateFileClientSide(file) {
  const ext = "." + file.name.split(".").pop().toLowerCase();
  if (!ALLOWED_EXTENSIONS.includes(ext)) {
    return "対応していないファイル形式です";
  }
  if (file.size > MAX_FILE_SIZE) {
    return "ファイルサイズは200MBまでです";
  }
  return null;
}

function setupDropzone(dropzoneId, inputId, onFile) {
  const dropzone = document.getElementById(dropzoneId);
  const input = document.getElementById(inputId);

  dropzone.addEventListener("click", () => input.click());
  input.addEventListener("change", () => {
    if (input.files[0]) onFile(input.files[0]);
  });
  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("drag");
  });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("drag"));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("drag");
    if (e.dataTransfer.files[0]) onFile(e.dataTransfer.files[0]);
  });
}

function renderEntriesTable(entries) {
  if (!entries || entries.length === 0) {
    return '<p class="success">不整合は検出されませんでした</p>';
  }
  const rows = entries
    .map(
      (e) =>
        `<tr><td>${e.category}</td><td>${e.severity}</td><td>${e.target_path}</td><td>${e.message}</td></tr>`
    )
    .join("");
  return `<table><thead><tr><th>category</th><th>severity</th><th>target_path</th><th>message</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function setupTabs() {
  const tabSingle = document.getElementById("tab-single");
  const tabDiff = document.getElementById("tab-diff");
  const panelSingle = document.getElementById("panel-single");
  const panelDiff = document.getElementById("panel-diff");

  tabSingle.addEventListener("click", () => {
    tabSingle.setAttribute("aria-selected", "true");
    tabDiff.setAttribute("aria-selected", "false");
    panelSingle.classList.add("active");
    panelDiff.classList.remove("active");
  });
  tabDiff.addEventListener("click", () => {
    tabDiff.setAttribute("aria-selected", "true");
    tabSingle.setAttribute("aria-selected", "false");
    panelDiff.classList.add("active");
    panelSingle.classList.remove("active");
  });
}

function setupSingleValidation() {
  const statusEl = document.getElementById("single-status");
  const resultEl = document.getElementById("single-result");

  setupDropzone("dropzone-single", "input-single", async (file) => {
    resultEl.innerHTML = "";
    const clientError = validateFileClientSide(file);
    if (clientError) {
      statusEl.innerHTML = `<p class="error">${clientError}</p>`;
      return;
    }
    statusEl.innerHTML = "<p>アップロード中...</p>";

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("/api/validate", { method: "POST", body: formData });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        statusEl.innerHTML = `<p class="error">${body.detail || "検証に失敗しました"}</p>`;
        return;
      }
      const data = await res.json();
      statusEl.innerHTML = "";
      resultEl.innerHTML = `
        <p>upAxis: ${data.up_axis} (${data.up_axis_is_explicit ? "明示" : "暗黙"}) /
           metersPerUnit: ${data.meters_per_unit} (${data.meters_per_unit_is_explicit ? "明示" : "暗黙"}) /
           prim_count: ${data.prim_count}</p>
        ${renderEntriesTable(data.entries)}
      `;
    } catch (err) {
      statusEl.innerHTML = `<p class="error">通信エラー: ${err}</p>`;
    }
  });
}

function setupDiffComparison() {
  const statusEl = document.getElementById("diff-status");
  const resultEl = document.getElementById("diff-result");
  let beforeFile = null;
  let afterFile = null;

  function tryDiff() {
    if (!beforeFile || !afterFile) return;
    runDiff();
  }

  setupDropzone("dropzone-before", "input-before", (file) => {
    const err = validateFileClientSide(file);
    if (err) {
      statusEl.innerHTML = `<p class="error">${err}</p>`;
      return;
    }
    beforeFile = file;
    tryDiff();
  });
  setupDropzone("dropzone-after", "input-after", (file) => {
    const err = validateFileClientSide(file);
    if (err) {
      statusEl.innerHTML = `<p class="error">${err}</p>`;
      return;
    }
    afterFile = file;
    tryDiff();
  });

  async function runDiff() {
    statusEl.innerHTML = "<p>アップロード中...</p>";
    resultEl.innerHTML = "";
    const formData = new FormData();
    formData.append("before", beforeFile);
    formData.append("after", afterFile);

    try {
      const res = await fetch("/api/diff", { method: "POST", body: formData });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        statusEl.innerHTML = `<p class="error">${body.detail || "差分比較に失敗しました"}</p>`;
        return;
      }
      const data = await res.json();
      statusEl.innerHTML = "";
      resultEl.innerHTML = `
        <p>prim_count: ${data.prim_count_before} -> ${data.prim_count_after} /
           material_count: ${data.material_count_before} -> ${data.material_count_after}</p>
        ${renderEntriesTable(data.entries)}
      `;
    } catch (err) {
      statusEl.innerHTML = `<p class="error">通信エラー: ${err}</p>`;
    }
  }
}

setupTabs();
setupSingleValidation();
setupDiffComparison();
