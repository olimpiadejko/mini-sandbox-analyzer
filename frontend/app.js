document.addEventListener("DOMContentLoaded", () => {
  let selectedFile = null;
  const fileInput = document.getElementById("file-input");
  const uploadContainer = document.getElementById("upload-container");

  if (!fileInput || !uploadContainer) {
    console.error("Nie znaleziono elementów input lub upload-container!");
    return;
  }

  fileInput.addEventListener("change", (event) => {
    const file = event.target.files[0];
    if (file) {
      displayFileCard(file);
    }
  });

  uploadContainer.addEventListener("dragover", (e) => {
    e.preventDefault();
    uploadContainer.style.borderColor = "var(--accent-color)";
  });

  uploadContainer.addEventListener("dragleave", (e) => {
    e.preventDefault();
    uploadContainer.style.borderColor = "";
  });

  uploadContainer.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadContainer.style.borderColor = "";
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      displayFileCard(file);
    }
  });

  function displayFileCard(file) {
    const startButton = document.getElementById("start-analysis-btn");

    if (!file.name.toLowerCase().endsWith(".exe")) {
      selectedFile = null;
      if (startButton) startButton.hidden = true;
      alert("Wybierz plik z rozszerzeniem .exe.");
      return;
    }
    selectedFile = file;

    const analysisStatus = document.getElementById("analysis-status");
    const progressText = document.getElementById("analysis-progress-text");
    const progressBar = document.getElementById("analysis-progress-bar");
    const eventsBody = document.getElementById("events-body");

    if (analysisStatus) analysisStatus.textContent = "Status: ⚪ Oczekiwanie na analizę";
    if (progressText) progressText.textContent = "0%";
    if (progressBar) progressBar.style.width = "0%";
    if (eventsBody) eventsBody.replaceChildren();

    if (startButton) {
      startButton.hidden = false;
      startButton.textContent = "Rozpocznij analizę";
    }

    const reportBtn = document.getElementById("download-report-btn");
    if (reportBtn) reportBtn.remove();

    const showBtn = document.getElementById("show-btn");
    if (showBtn) {
      showBtn.style.display = "inline-block";
      showBtn.textContent = "Zmień plik";
    }

    // Przywracamy widoczność ikony i napisów w razie wyboru innego pliku
    const uploadIcon = uploadContainer.querySelector(".upload-icon");
    const uploadTitle = uploadContainer.querySelector("h3");
    const uploadSubtitle = uploadContainer.querySelector("p");
    if (uploadIcon) uploadIcon.style.display = "";
    if (uploadTitle) uploadTitle.style.display = "";
    if (uploadSubtitle) uploadSubtitle.style.display = "";

    let existingCard = document.querySelector(".file-card");
    if (existingCard) existingCard.remove();

    let formattedSize = "";
    if (file.size < 1024 * 1024) {
      formattedSize = (file.size / 1024).toFixed(1) + " KB";
    } else {
      formattedSize = (file.size / (1024 * 1024)).toFixed(1) + " MB";
    }

    const fileCard = document.createElement("div");
    fileCard.className = "file-card";
    fileCard.innerHTML = `
        <div class="file-icon">📄</div>
        <div class="file-info">
            <h4>${file.name}</h4>
            <p>Rozmiar: ${formattedSize} | Typ: ${file.type || "Aplikacja wykonywalna (.exe)"}</p>
        </div>
    `;
    uploadContainer.appendChild(fileCard);
  }

  const startButton = document.getElementById("start-analysis-btn");
  const eventsBody = document.getElementById("events-body");
  const analysisStatus = document.getElementById("analysis-status");
  const progressText = document.getElementById("analysis-progress-text");
  const progressBar = document.getElementById("analysis-progress-bar");

  function updateProgress(percent, statusMessage) {
    if (progressText) progressText.textContent = percent + "%";
    if (progressBar) progressBar.style.width = percent + "%";
    if (analysisStatus && statusMessage) analysisStatus.textContent = statusMessage;
  }

  if (startButton && eventsBody) {
    startButton.addEventListener("click", async () => {
      if (startButton.textContent.includes("Wybierz inny")) {
        fileInput.value = "";
        fileInput.click();
        return;
      }

      eventsBody.replaceChildren();
      startButton.disabled = true;

      try {
        if (!selectedFile) {
          throw new Error("Najpierw wybierz plik EXE.");
        }

        // UKRYWAMY zarówno ikonę folderu, jak i wszystkie napisy instrukcyjne po kliknięciu startu
        const uploadIcon = uploadContainer.querySelector(".upload-icon");
        const uploadTitle = uploadContainer.querySelector("h3");
        const uploadSubtitle = uploadContainer.querySelector("p");
        if (uploadIcon) uploadIcon.style.display = "none";
        if (uploadTitle) uploadTitle.style.display = "none";
        if (uploadSubtitle) uploadSubtitle.style.display = "none";

        updateProgress(15, "Status: 🟡 Przygotowanie pliku do analizy...");
        await new Promise(r => setTimeout(r, 200));

        const formData = new FormData();
        formData.append("file", selectedFile);

        updateProgress(40, `Status: 🟡 Przesyłanie pliku ${selectedFile.name} na serwer...`);

        const response = await fetch("/api/analyze", {
          method: "POST",
          body: formData
        });

        const contentType = response.headers.get("content-type");
        if (!contentType || !contentType.includes("application/json")) {
          throw new Error(`Serwer zwrócił nieprawidłową odpowiedź (status: ${response.status})`);
        }

        updateProgress(75, "Status: 🟡 Wykonywanie analizy statycznej i nagłówka PE...");

        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.detail || `Błąd serwera: ${response.status}`);
        }

        updateProgress(100, "Status: 🟢 " + data.message);

        data.events.forEach((event) => {
          const row = document.createElement("tr");

          const timeCell = document.createElement("td");
          timeCell.textContent = event.time;

          const messageCell = document.createElement("td");
          messageCell.innerHTML = event.message;

          const typeCell = document.createElement("td");
          const tagSpan = document.createElement("span");
          tagSpan.className = "tag";

          if (event.type === "Proces") {
            tagSpan.classList.add("tag-process");
          } else if (event.type === "Plik") {
            tagSpan.classList.add("tag-file");
          } else if (event.type === "Sieć") {
            tagSpan.classList.add("tag-network");
          } else {
            tagSpan.classList.add("tag-process");
          }

          tagSpan.textContent = event.type;
          typeCell.appendChild(tagSpan);

          row.append(timeCell, messageCell, typeCell);
          eventsBody.appendChild(row);
        });

        startButton.textContent = "Wybierz inny program do analizy";

        const showBtn = document.getElementById("show-btn");
        if (showBtn) showBtn.style.display = "none";

        let reportBtn = document.getElementById("download-report-btn");
        if (!reportBtn) {
          reportBtn = document.createElement("button");
          reportBtn.type = "button";
          reportBtn.id = "download-report-btn";
          reportBtn.className = "btn-submit";
          reportBtn.style.backgroundColor = "var(--success)";
          reportBtn.textContent = "Pobierz raport analizy";

          reportBtn.addEventListener("click", () => {
            alert("Funkcja pobierania raportu będzie dostępna w kolejnych etapach!");
          });

          startButton.parentElement.appendChild(reportBtn);
        }

      } catch (error) {
        console.error("Błąd podczas analizy:", error);
        if (analysisStatus) analysisStatus.textContent = "Status: 🔴 Wystąpił błąd podczas analizy.";
        if (progressText) progressText.textContent = "Błąd";
        if (progressBar) progressBar.style.width = "0%";

        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 3;
        cell.textContent = error.message || "Wystąpił błąd podczas komunikacji z serwerem.";
        row.appendChild(cell);
        eventsBody.appendChild(row);
      } finally {
        startButton.disabled = false;
      }
    });
  }

  // Obsługa zakładek (filtrowanie tabeli)
  const tabBtns = document.querySelectorAll(".tab-btn");
  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      tabBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");

      const filter = btn.textContent.trim().split(" ")[0];
      const rows = document.querySelectorAll("#events-body tr");

      rows.forEach(row => {
        const typeCell = row.querySelector("td:nth-child(3)");
        if (!typeCell) return;
        const typeText = typeCell.textContent.trim();
        if (filter === "Wszystkie" || typeText.includes(filter)) {
          row.style.display = "";
        } else {
          row.style.display = "none";
        }
      });
    });
  });
});