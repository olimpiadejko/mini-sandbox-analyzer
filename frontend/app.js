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

    startButton.hidden = false;
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
});
