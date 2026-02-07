// Toast notification helper
function showToast(message, duration) {
    duration = duration || 3000;
    var container = document.getElementById("toast-container");
    if (!container) return;

    var toast = document.createElement("div");
    toast.className = "bg-gray-800 text-white px-4 py-3 rounded-lg shadow-lg text-sm animate-fade-in";
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(function () {
        toast.style.opacity = "0";
        toast.style.transition = "opacity 0.3s";
        setTimeout(function () { toast.remove(); }, 300);
    }, duration);
}

// Listen for HTMX events
document.addEventListener("htmx:afterSwap", function (evt) {
    var trigger = evt.detail.xhr.getResponseHeader("HX-Trigger");
    if (trigger) {
        try {
            var data = JSON.parse(trigger);
            if (data.showToast) {
                showToast(data.showToast);
            }
        } catch (e) {
            // Not JSON, ignore
        }
    }
});
