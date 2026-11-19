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
      fileInput.value = "";
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
    if (showBtn) showBtn.style.display = "inline-block";

    if (!file.name.toLowerCase().endsWith(".exe")) {
      selectedFile = null;
      if (startButton) startButton.hidden = true;

      const reportBtn = document.getElementById("download-report-btn");
      if (reportBtn) reportBtn.remove();

      showError("Dozwolone są wyłącznie pliki z rozszerzeniem .exe.");
      return;
    }

    const maxSizeBytes = 150 * 1024 * 1024; // 150 MB
    if (file.size === 0 || file.size > maxSizeBytes) {
      selectedFile = null;
      if (startButton) startButton.hidden = true;

      const reportBtn = document.getElementById("download-report-btn");
      if (reportBtn) reportBtn.remove();

      showError("Plik jest pusty lub przekracza dozwolony limit rozmiaru (maksymalnie 150 MB).");
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
        formData.append("custom_apis", localStorage.getItem("analyzer_apis") || "");
        formData.append("timeout", localStorage.getItem("analyzer_timeout") || "5");
        formData.append("autodelete", localStorage.getItem("analyzer_autodelete") || "true");

        updateProgress(45, `Status: 🟡 Analiza statyczna i uruchomienie próbki ${selectedFile.name} w piaskownicy VM...`);

        const response = await fetch("/api/analyze", {
          method: "POST",
          body: formData
        });

        const contentType = response.headers.get("content-type");
        if (!contentType || !contentType.includes("application/json")) {
          throw new Error(`Serwer zwrócił nieprawidłową odpowiedź (status: ${response.status})`);
        }

        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.detail || `Błąd serwera (status: ${response.status})`);
        }

        updateProgress(90, "Status: 🟡 Przetwarzanie wyników i logów Sysmon...");

        const riskBox = document.getElementById("risk-card-box");
        const riskLevelText = document.getElementById("risk-card-level");
        const riskDescText = document.getElementById("risk-card-desc");
        const riskIconBox = document.getElementById("risk-card-icon");

        if (riskBox && riskLevelText) {
          riskBox.style.display = "flex";
          riskBox.className = "risk-card-container";

          if (data.risk_level === "Niskie") {
            riskBox.classList.add("risk-card-low");
            riskLevelText.innerHTML = 'Poziom ryzyka: <span style="color: var(--success);">Niskie</span>';
            riskIconBox.textContent = "✅";
            riskDescText.textContent = "Plik nie wykazuje cech złośliwości. Standardowe struktury PE i bezpieczne importy.";
          } else if (data.risk_level === "Średnie") {
            riskBox.classList.add("risk-card-medium");
            riskLevelText.innerHTML = 'Poziom ryzyka: <span style="color: var(--warning);">Średnie</span>';
            riskIconBox.textContent = "⚠️";
            riskDescText.textContent = "Wykryto funkcje dynamicznego ładowania API lub podwyższoną entropię sekcji. Zalecana ostrożność.";
          } else {
            riskBox.classList.add("risk-card-high");
            riskLevelText.innerHTML = 'Poziom ryzyka: <span style="color: #f87171;">Wysokie!</span>';
            riskIconBox.textContent = "🚨";
            riskDescText.textContent = "Wykryto potencjalnie niebezpieczne mechanizmy (np. iniekcje kodu, wysoka entropia packerów).";
          }
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
          } else if (event.type === "Zasoby") {
            tagSpan.classList.add("tag-resources");
          } else {
            tagSpan.classList.add("tag-process");
          }

          tagSpan.textContent = event.type;
          typeCell.appendChild(tagSpan);

          row.append(timeCell, messageCell, typeCell);
          eventsBody.appendChild(row);
        });

        updateTabCounts();

        if (localStorage.getItem("analyzer_sound") !== "false") {
          playNotificationSound();
        }

        if (localStorage.getItem("analyzer_autoreport") === "true" && data.id) {
          window.location.href = `/api/report/${data.id}`;
        }

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

          reportBtn.addEventListener("click", async () => {
            try {
              const res = await fetch("/api/history");
              const histData = await res.json();

              if (histData.history && histData.history.length > 0) {
                const latestId = histData.history[0].id;
                window.location.href = `/api/report/${latestId}`;
              } else {
                showError("Nie znaleziono żadnej historii analiz.");
              }
            } catch (err) {
              showError("Nie udało się pobrać raportu.");
            }
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

function showError(message, isSuccess = false) {
  const existingError = document.querySelector(".error-banner");
  if (existingError) existingError.remove();

  const uploadContainer = document.getElementById("upload-container");
  if (!uploadContainer) return;

  const icon = isSuccess ? "✅" : "❌";
  const bannerClass = isSuccess ? "error-banner success-banner" : "error-banner";

  const errorBanner = document.createElement("div");
  errorBanner.className = bannerClass;
  errorBanner.innerHTML = `
    <div class="error-banner-content">
      <span>${icon}</span>
      <span>${message}</span>
    </div>
    <button class="error-close-btn" onclick="this.parentElement.remove()">&times;</button>
  `;

  uploadContainer.appendChild(errorBanner);

  setTimeout(() => {
    errorBanner.classList.add("fade-out");
    setTimeout(() => {
      if (errorBanner.parentElement) {
        errorBanner.remove();
      }
    }, 300);
  }, 5000);
}

const historyModal = document.getElementById("history-modal");
const settingsModal = document.getElementById("settings-modal");

const historyLink = document.getElementById("nav-history");
if (historyLink) {
  historyLink.addEventListener("click", async (e) => {
    e.preventDefault();
    if (historyModal) historyModal.style.display = "flex";

    try {
      const response = await fetch("/api/history");
      const data = await response.json();
      const historyBody = document.getElementById("history-body");
      if (historyBody) {
        historyBody.replaceChildren();

        if (data.history.length === 0) {
          const row = document.createElement("tr");
          row.innerHTML = `<td colspan="5" style="text-align: center; color: var(--text-muted);">Brak zapisanych analiz w historii.</td>`;
          historyBody.appendChild(row);
          return;
        }

        data.history.forEach(item => {
          const row = document.createElement("tr");

          let riskClass = "risk-low-text";
          if (item.risk_level === "Średnie") riskClass = "risk-medium-text";
          if (item.risk_level === "Wysokie") riskClass = "risk-high-text";

          row.innerHTML = `
            <td>${item.timestamp}</td>
            <td><strong>${item.filename}</strong></td>
            <td>${item.size_mb} MB</td>
            <td style="text-align: center;"><span class="${riskClass}">${item.risk_level}</span></td>
            <td style="text-align: center;">
              <a href="/api/report/${item.id}" class="btn-submit" style="padding: 4px 10px; font-size: 0.8rem; text-decoration: none; display: inline-block; margin-top: 0;" download>
                Pobierz raport
              </a>
            </td>
          `;
          historyBody.appendChild(row);
        });
      }
    } catch (err) {
      console.error("Błąd pobierania historii:", err);
    }
  });
}

const settingsLink = document.getElementById("nav-settings");
if (settingsLink) {
  settingsLink.addEventListener("click", (e) => {
    e.preventDefault();
    if (settingsModal) settingsModal.style.display = "flex";
  });
}

function closeModals() {
  if (historyModal) historyModal.style.display = "none";
  if (settingsModal) settingsModal.style.display = "none";
}

window.addEventListener("load", () => {
  if (localStorage.getItem("analyzer_timeout")) {
    document.getElementById("setting-timeout").value = localStorage.getItem("analyzer_timeout");
  }
  if (localStorage.getItem("analyzer_apis") !== null) {
    document.getElementById("setting-suspicious-apis").value = localStorage.getItem("analyzer_apis");
  }
  if (localStorage.getItem("analyzer_autodelete") !== null) {
    document.getElementById("setting-autodelete").checked = localStorage.getItem("analyzer_autodelete") === "true";
  }
  if (localStorage.getItem("analyzer_autoreport") !== null) {
    document.getElementById("setting-autoreport").checked = localStorage.getItem("analyzer_autoreport") === "true";
  }
  if (localStorage.getItem("analyzer_sound") !== null) {
    document.getElementById("setting-sound").checked = localStorage.getItem("analyzer_sound") === "true";
  }
});

function saveSettings() {
  const timeout = document.getElementById("setting-timeout").value;
  const suspiciousApis = document.getElementById("setting-suspicious-apis").value;
  const autoDelete = document.getElementById("setting-autodelete").checked;
  const autoReport = document.getElementById("setting-autoreport").checked;
  const sound = document.getElementById("setting-sound").checked;

  localStorage.setItem("analyzer_timeout", timeout);
  localStorage.setItem("analyzer_apis", suspiciousApis);
  localStorage.setItem("analyzer_autodelete", autoDelete);
  localStorage.setItem("analyzer_autoreport", autoReport);
  localStorage.setItem("analyzer_sound", sound);

  closeModals();
  showError("Ustawienia zostały zapisane pomyślnie!", true);
}

function playNotificationSound() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const notes = [523.25, 659.25, 783.99];
    notes.forEach((freq, index) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "triangle";
      const startTime = ctx.currentTime + index * 0.1;
      osc.frequency.setValueAtTime(freq, startTime);
      gain.gain.setValueAtTime(0.12, startTime);
      gain.gain.exponentialRampToValueAtTime(0.0001, startTime + 0.4);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(startTime);
      osc.stop(startTime + 0.4);
    });
  } catch (e) {
    console.warn("Przeglądarka zablokowała dźwięk:", e);
  }
}
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeModals();
});

window.addEventListener("click", (e) => {
  if (e.target === historyModal || e.target === settingsModal) {
    closeModals();
  }
});