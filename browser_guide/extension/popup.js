const statusText = document.getElementById("text");
const indicator = document.getElementById("indicator");

function updateStatus() {
    chrome.runtime.sendMessage({ type: "status_check" }, (response) => {
        if (chrome.runtime.lastError) {
            statusText.innerText = "Err: " + chrome.runtime.lastError.message;
            indicator.style.background = "orange";
            return;
        }

        if (response && response.status === "connected") {
            statusText.innerText = "Connected";
            indicator.classList.add("connected");
        } else {
            statusText.innerText = "Disconnected";
            indicator.classList.remove("connected");
        }
    });
}

// Check on load
updateStatus();

// Check every 2 seconds
setInterval(updateStatus, 2000);

// Allow clicking to retry
document.body.addEventListener('click', () => {
    chrome.runtime.sendMessage({ type: "connect" });
    setTimeout(updateStatus, 500);
});
