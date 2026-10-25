document.addEventListener("DOMContentLoaded", () => {
  let selectedFile = null;
  const fileInput = document.getElementById("file-input");
  const uploadContainer = document.getElementById("upload-container");
  const showBtn = document.getElementById("show-btn");
  const startButton = document.getElementById("start-analysis-btn");
  const eventsBody = document.getElementById("events-body");
  const analysisStatus = document.getElementById("analysis-status");
  const progressText = document.getElementById("analysis-progress-text");
  const progressBar = document.getElementById("analysis-progress-bar");

  if (!fileInput || !uploadContainer) {
    console.error("Nie znaleziono elementów input lub upload-container!");
    return;
  }

  // Kliknięcie w przycisk "Wybierz plik" zawsze otwiera okno wyboru
  if (showBtn) {
    showBtn.addEventListener("click", () => {
      fileInput.value = ""; // Resetujemy input, aby można było wybrać ten sam plik ponownie
      fileInput.click();
    });
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
    // Zawsze dbamy o to, aby przycisk wyboru pliku był widoczny
    if (showBtn) showBtn.style.display = "inline-block";

    if (!file.name.toLowerCase().endsWith(".exe")) {
      selectedFile = null;
      if (startButton) startButton.hidden = true;

      // Usuwamy przycisk raportu, jeśli istniał
      const reportBtn = document.getElementById("download-report-btn");
      if (reportBtn) reportBtn.remove();

      showError("Dozwolone są wyłącznie pliki z rozszerzeniem .exe.");
      return;
    }
    selectedFile = file;

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

    // Przywracamy widoczność napisów instrukcyjnych
    const uploadTitle = uploadContainer.querySelector("h3");
    const uploadSubtitle = uploadContainer.querySelector("p");
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

    const fileIcon = document.createElement("div");
    fileIcon.className = "file-icon";
    fileIcon.textContent = "📄";

    const fileInfo = document.createElement("div");
    fileInfo.className = "file-info";

    const fileName = document.createElement("h4");
    fileName.textContent = file.name;

    const fileDetails = document.createElement("p");
    fileDetails.textContent = `Rozmiar: ${formattedSize} | Typ: ${file.type || "Aplikacja wykonywalna (.exe)"}`;

    fileInfo.append(fileName, fileDetails);
    fileCard.append(fileIcon, fileInfo);
    uploadContainer.appendChild(fileCard);
  }

  function updateProgress(percent, statusMessage) {
    if (progressText) progressText.textContent = percent + "%";
    if (progressBar) progressBar.style.width = percent + "%";
    if (analysisStatus && statusMessage) analysisStatus.textContent = statusMessage;
  }

  function updateTabCounts() {
    const rows = [...eventsBody.querySelectorAll("tr")];

    const counts = {
      all: rows.length,
      files: 0,
      processes: 0,
      network: 0,
      resources: 0
    };

    rows.forEach((row) => {
      const category = row.querySelector("td:nth-child(3) .tag");
      if (!category) return;
      const type = category.textContent.trim();

      if (type === "Plik") counts.files++;
      else if (type === "Proces") counts.processes++;
      else if (type === "Sieć") counts.network++;
      else if (type === "Zasoby") counts.resources++;
    });

    const countAll = document.getElementById("count-all");
    const countFiles = document.getElementById("count-files");
    const countProcesses = document.getElementById("count-processes");
    const countNetwork = document.getElementById("count-network");
    const countResources = document.getElementById("count-resources");

    if (countAll) countAll.textContent = counts.all;
    if (countFiles) countFiles.textContent = counts.files;
    if (countProcesses) countProcesses.textContent = counts.processes;
    if (countNetwork) countNetwork.textContent = counts.network;
    if (countResources) countResources.textContent = counts.resources;
  }

  if (startButton && eventsBody) {
    startButton.addEventListener("click", async () => {
      eventsBody.replaceChildren();
      startButton.disabled = true;

      try {
        if (!selectedFile) {
          throw new Error("Najpierw wybierz plik EXE.");
        }

        const uploadTitle = uploadContainer.querySelector("h3");
        const uploadSubtitle = uploadContainer.querySelector("p");
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
          messageCell.textContent = event.message;

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

        updateTabCounts();

        // Po zakończeniu analizy ukrywamy przycisk startu, a pokazujemy przycisk wyboru innego pliku
        startButton.hidden = true;
        if (showBtn) {
          showBtn.style.display = "inline-block";
          showBtn.textContent = "Wybierz inny program";
        }

        let reportBtn = document.getElementById("download-report-btn");
        if (!reportBtn) {
          reportBtn = document.createElement("button");
          reportBtn.type = "button";
          reportBtn.id = "download-report-btn";
          reportBtn.className = "btn-submit";
          reportBtn.style.backgroundColor = "var(--success)";
          reportBtn.textContent = "Pobierz raport analizy";

          reportBtn.addEventListener("click", () => {
            showError("Funkcja pobierania raportu będzie dostępna w kolejnych etapach!");
          });

          startButton.parentElement.appendChild(reportBtn);
        }

      } catch (error) {
        console.error("Błąd podczas analizy:", error);
        if (analysisStatus) analysisStatus.textContent = "Status: 🔴 Wystąpił błąd podczas analizy.";
        if (progressText) progressText.textContent = "Błąd";
        if (progressBar) progressBar.style.width = "0%";

        showError(error.message || "Wystąpił błąd podczas komunikacji z serwerem.");

        if (startButton) {
          startButton.hidden = false;
          startButton.textContent = "Rozpocznij analizę";
        }
        if (showBtn) showBtn.style.display = "inline-block";
      } finally {
        startButton.disabled = false;
      }
    });
  }

  // Obsługa zakładek (filtrowanie tabeli)
  const tabBtns = document.querySelectorAll(".tab-btn");

  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");

      const filter = btn.dataset.filter;
      const rows = document.querySelectorAll("#events-body tr");

      rows.forEach((row) => {
        const tag = row.querySelector("td:nth-child(3) .tag");
        const type = tag ? tag.textContent.trim() : "";

        if (
          filter === "all" ||
          (filter === "Plik" && type === "Plik") ||
          (filter === "Proces" && type === "Proces") ||
          (filter === "Sieć" && type === "Sieć") ||
          (filter === "Zasoby" && type === "Zasoby")
        ) {
          row.style.display = "";
        } else {
          row.style.display = "none";
        }
      });
    });
  });
});

function showError(message) {
  // Usuwamy poprzedni błąd, jeśli już istnieje
  const existingError = document.querySelector(".error-banner");
  if (existingError) existingError.remove();

  const uploadContainer = document.getElementById("upload-container");
  if (!uploadContainer) return;

  const errorBanner = document.createElement("div");
  errorBanner.className = "error-banner";
  errorBanner.innerHTML = `
    <div class="error-banner-content">
      <span>❌</span>
      <span>${message}</span>
    </div>
    <button class="error-close-btn" onclick="this.parentElement.remove()">&times;</button>
  `;

  uploadContainer.appendChild(errorBanner);

  // AUTOMATYCZNE ZNIKANIE Z PŁYNNYM WYGASZANIEM PO 5 SEKUNDACH
  setTimeout(() => {
    // Dodajemy klasę uruchamiającą animację znikania
    errorBanner.classList.add("fade-out");

    // Czekamy 300ms (tyle co animacja CSS) i dopiero wtedy usuwamy element z DOM
    setTimeout(() => {
      if (errorBanner.parentElement) {
        errorBanner.remove();
      }
    }, 300);

  }, 5000);
}


const historyLink = document.getElementById("nav-history");
if (historyLink) {
  historyLink.addEventListener("click", (e) => {
    e.preventDefault();
    showError("Panel Historii będzie dostępny w kolejnych etapach!");
  });
}

const settingsLink = document.getElementById("nav-settings");
if (settingsLink) {
  settingsLink.addEventListener("click", (e) => {
    e.preventDefault();
    showError("Panel Ustawień będzie dostępny w kolejnych etapach!");
  });
}