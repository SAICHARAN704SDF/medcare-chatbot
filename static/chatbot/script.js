// ---------------- Sentiment Analysis ----------------
async function analyzeText() {
  const text = document.getElementById("userInput").value;

  const response = await fetch("/api/analyze-sentiment", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text })
  });

  const data = await response.json();

  if (data.error) {
    alert(data.error);
    return;
  }

  document.getElementById("result").innerText =
    `${data.message} (Label: ${data.label}, Score: ${data.score.toFixed(2)})`;

  loadHistory(); // refresh history after submission
}

async function loadHistory() {
  const res = await fetch("/api/history");
  const history = await res.json();

  let historyList = document.getElementById("history");
  historyList.innerHTML = "";
  history.forEach(item => {
    let li = document.createElement("li");
    li.textContent = `${item.text} → ${item.label} (${item.score.toFixed(2)})`;
    historyList.appendChild(li);
  });
}

// ---------------- Login & Signup Logic ----------------
document.addEventListener("DOMContentLoaded", () => {

  // -------- Login Form --------
  const loginForm = document.getElementById("loginForm");
  if (loginForm) {
    loginForm.addEventListener("submit", async function (e) {
      e.preventDefault();

      const username = document.getElementById("username").value.trim();
      const password = document.getElementById("password").value.trim();

      try {
        const response = await fetch("/api/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, password })
        });

        const data = await response.json();

        if (response.ok && data.status === "success") {
          localStorage.setItem("token", data.token);
          localStorage.setItem("user_id", data.user_id);

          window.location.href = "/dashboard"; // redirect after login
        } else {
          alert(data.error || "Login failed");
        }
      } catch (err) {
        console.error(err);
        alert("Server error. Please try again.");
      }
    });
  }

  // -------- Signup Form --------
  const signupForm = document.getElementById("signupForm");
  if (signupForm) {
    signupForm.addEventListener("submit", async function (e) {
      e.preventDefault();

      const username = document.getElementById("username").value.trim();
      const password = document.getElementById("password").value.trim();

      try {
        const response = await fetch("/api/signup", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, password })
        });

        const data = await response.json();

        if (response.ok && data.status === "success") {
          alert("Signup successful! Please login.");
          window.location.href = "/login"; // redirect after signup
        } else {
          alert(data.error || "Signup failed");
        }
      } catch (err) {
        console.error(err);
        alert("Server error. Please try again.");
      }
    });
  }

  // -------- Auto-load history on Dashboard --------
  if (document.getElementById("history")) {
    loadHistory();
  }
});
