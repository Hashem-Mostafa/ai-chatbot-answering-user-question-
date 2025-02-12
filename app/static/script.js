document.getElementById("upload-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const formData = new FormData();
    formData.append("file", e.target.file.files[0]);

    const response = await fetch("/upload", {
        method: "POST",
        body: formData,
    });

    const result = await response.json();
    alert(result.message || result.error);
});

document.getElementById("send-button").addEventListener("click", async () => {
    const input = document.getElementById("chat-input");
    const query = input.value.trim();

    if (!query) return;

    const response = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
    });

    const result = await response.json();
    const chatMessages = document.getElementById("chat-messages");
    chatMessages.innerHTML += `<div><strong>You:</strong> ${query}</div>`;
    chatMessages.innerHTML += `<div><strong>Bot:</strong> ${result.response}</div>`;
    input.value = "";
});