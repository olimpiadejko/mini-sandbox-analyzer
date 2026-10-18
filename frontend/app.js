document.addEventListener("DOMContentLoaded", () => {
  // Pobieramy istniejący input pliku oraz kontener uploadu z index.html
  const fileInput = document.getElementById("file-input");
  const uploadContainer = document.getElementById("upload-container");

  if (!fileInput || !uploadContainer) {
    console.error("Nie znaleziono elementów input lub upload-container!");
    return;
  }

  // Gdy użytkownik wybierze plik przez okno dialogowe
  fileInput.addEventListener("change", (event) => {
    const file = event.target.files[0];
    if (file) {
      displayFileCard(file);
    }
  });

  // Obsługa przeciągania pliku (Drag & Drop)
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

  // Funkcja generująca i wyświetlająca kartę pliku
  function displayFileCard(file) {
    const startButton = document.getElementById("start-analysis-btn");

    if (!file.name.toLowerCase().endsWith(".exe")) {
      startButton.hidden = true;
      alert("Wybierz plik z rozszerzeniem .exe.");
      return;
    }

    // Resetujemy status i pasek po wybraniu nowego pliku
    const analysisStatus = document.getElementById("analysis-status");
    const progressText = document.getElementById("analysis-progress-text");
    const progressBar = document.getElementById("analysis-progress-bar");
    const eventsBody = document.getElementById("events-body");

    if (analysisStatus) {
      analysisStatus.textContent = "Status: ⚪ Oczekiwanie na analizę";
    }

    if (progressText) {
      progressText.textContent = "0%";
    }

    if (progressBar) {
      progressBar.style.width = "0%";
    }

    if (eventsBody) {
      eventsBody.replaceChildren();
    }


    startButton.hidden = false;
    const showBtn = document.getElementById("show-btn");
    if (showBtn) {
      showBtn.textContent = "Zmień plik";
    }
    // Sprawdzamy czy karta już istnieje, jak tak - usuwamy ją
    let existingCard = document.querySelector(".file-card");
    if (existingCard) {
      existingCard.remove();
    }

    // Formatujemy rozmiar pliku na czytelny format (KB / MB)
    let formattedSize = "";
    if (file.size < 1024 * 1024) {
      formattedSize = (file.size / 1024).toFixed(1) + " KB";
    } else {
      formattedSize = (file.size / (1024 * 1024)).toFixed(1) + " MB";
    }

    // Tworzymy element karty
    const fileCard = document.createElement("div");
    fileCard.className = "file-card";
    fileCard.innerHTML = `
        <div class="file-icon">📄</div>
        <div class="file-info">
            <h4>${file.name}</h4>
            <p>Rozmiar: ${formattedSize} | Typ: ${file.type || "Aplikacja wykonywalna (.exe)"}</p>
        </div>
    `;

    // Wstawiamy kartę do kontenera uploadu
    uploadContainer.appendChild(fileCard);
  }

  const startButton = document.getElementById("start-analysis-btn");
  const eventsBody = document.getElementById("events-body");
  const analysisStatus = document.getElementById("analysis-status");
  const progressText = document.getElementById("analysis-progress-text");
  const progressBar = document.getElementById("analysis-progress-bar");

  if (startButton && eventsBody) {
    startButton.addEventListener("click", async () => {
      eventsBody.replaceChildren(); // Czyści poprzednie logi
      startButton.disabled = true; // Blokuje przycisk, aby uniknąć wielokrotnego kliknięcia

      if (analysisStatus) {
        analysisStatus.textContent = "Status: 🟡 Pobieranie wyników...";
      }
      if (progressText) {
        progressText.textContent = "0%";
      }
      if (progressBar) {
        progressBar.style.width = "0%";
      }

      try {
        const response = await fetch("/api/demo-analysis");

        if (!response.ok) {
          throw new Error(`Błąd serwera: ${response.status}`);
        }

        const data = await response.json();

        if (analysisStatus) {
          analysisStatus.textContent = "Status: 🟢 " + data.message;
        }
        if (progressText) {
          progressText.textContent = "100%";
        }
        if (progressBar) {
          progressBar.style.width = "100%";
        }

        data.events.forEach((event) => {
          const row = document.createElement("tr");

          const timeCell = document.createElement("td");
          timeCell.textContent = event.time;

          const messageCell = document.createElement("td");
          messageCell.textContent = event.message;

          const typeCell = document.createElement("td");
          typeCell.textContent = event.type;

          row.append(timeCell, messageCell, typeCell);
          eventsBody.appendChild(row);
        });
      } catch (error) {
        console.error("Błąd podczas pobierania danych:", error);

        if (analysisStatus) {
          analysisStatus.textContent = "Status: 🔴 Wystąpił błąd podczas pobierania danych.";
        }

        if (progressText) {
          progressText.textContent = "Błąd";
        }
        if (progressBar) {
          progressBar.style.width = "0%";
        }

        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 3;
        cell.textContent = "Nie udało się pobrać danych z serwera.";
        row.appendChild(cell);
        eventsBody.appendChild(row);
      } finally {
        startButton.disabled = false; // Odblokowuje przycisk po zakończeniu analizy
      }
    });
  }




});
