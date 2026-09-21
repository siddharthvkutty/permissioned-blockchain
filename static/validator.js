const proposeBtn = document.getElementById("btn-propose");
const statusEl = document.getElementById("propose-status");
const resultEl = document.getElementById("propose-result");

if (proposeBtn) {
  proposeBtn.addEventListener("click", async () => {
    proposeBtn.disabled = true;
    statusEl.textContent = "Proposing block...";
    resultEl.style.display = "none";
    try {
      const res = await fetch("/validator/propose", { method: "POST" });
      const data = await res.json();
      if (data.ok) {
        statusEl.textContent = `Block #${data.block.index} accepted. Reward: ${data.reward} coins.`;
        resultEl.style.display = "block";
        resultEl.textContent = JSON.stringify(data.block, null, 2);
      } else {
        statusEl.textContent = `Could not propose: ${data.error}`;
        proposeBtn.disabled = false;
      }
    } catch (e) {
      statusEl.textContent = "Network error while proposing: " + e;
      proposeBtn.disabled = false;
    }
  });
}

// If we're waiting on someone else's slot, count down locally and reload
// once their window expires - this is what lets the page pick up
// fallback eligibility automatically, without the user needing to
// manually refresh to notice they've become eligible.
const countdownEl = document.getElementById("countdown");
if (countdownEl) {
  let seconds = parseFloat(countdownEl.dataset.seconds);
  const valueEl = document.getElementById("countdown-value");
  const timer = setInterval(() => {
    seconds -= 1;
    if (seconds <= 0) {
      clearInterval(timer);
      location.reload();
    } else if (valueEl) {
      valueEl.textContent = Math.ceil(seconds);
    }
  }, 1000);
}
