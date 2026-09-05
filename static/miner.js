const certBtn = document.getElementById("btn-cert");
const mineBtn = document.getElementById("btn-mine");
const certBox = document.getElementById("cert-box");
const statusEl = document.getElementById("mine-status");
const resultEl = document.getElementById("mine-result");

function renderCert(cert) {
  if (!cert) {
    certBox.classList.remove("has-cert");
    certBox.innerHTML = '<p class="muted">No active certificate.</p>';
    mineBtn.disabled = true;
    return;
  }
  certBox.classList.add("has-cert");
  certBox.innerHTML = `
    <div><span class="muted">Certificate ID</span><code>${cert.cert_id.slice(0, 24)}...</code></div>
    <div><span class="muted">For block</span><code>#${cert.block_index}</code></div>
    <div><span class="muted">Status</span><span class="badge badge-ok">active</span></div>
  `;
  mineBtn.disabled = false;
}

// If the server already rendered an active certificate, enable mining immediately.
if (certBox.classList.contains("has-cert")) {
  mineBtn.disabled = false;
}

certBtn.addEventListener("click", async () => {
  certBtn.disabled = true;
  statusEl.textContent = "Requesting certificate from the MCA...";
  resultEl.style.display = "none";
  try {
    const res = await fetch("/miner/certificate", { method: "POST" });
    const data = await res.json();
    if (data.ok) {
      renderCert(data.certificate);
      statusEl.textContent = "Certificate issued. You may now mine.";
    } else {
      statusEl.textContent = "Error: " + data.error;
    }
  } catch (e) {
    statusEl.textContent = "Network error requesting certificate: " + e;
  } finally {
    certBtn.disabled = false;
  }
});

mineBtn.addEventListener("click", async () => {
  mineBtn.disabled = true;
  certBtn.disabled = true;
  statusEl.textContent = "Mining... (light proof-of-work, should only take a moment)";
  resultEl.style.display = "none";
  const started = performance.now();
  try {
    const res = await fetch("/miner/mine", { method: "POST" });
    const data = await res.json();
    const seconds = ((performance.now() - started) / 1000).toFixed(2);
    if (data.ok) {
      statusEl.textContent = `Block #${data.block.index} mined in ${seconds}s. Reward: ${data.reward} coins.`;
      resultEl.style.display = "block";
      resultEl.textContent = JSON.stringify(data.block, null, 2);
      renderCert(null);
    } else {
      statusEl.textContent = `Mining failed: ${data.error}`;
      if (String(data.error).toLowerCase().includes("certificate")) {
        renderCert(null);
      }
    }
  } catch (e) {
    statusEl.textContent = "Network error while mining: " + e;
  } finally {
    certBtn.disabled = false;
  }
});
