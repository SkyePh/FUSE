document.addEventListener("DOMContentLoaded", function() {
  const rows = document.querySelectorAll("tbody tr");
  const rowsPerPage = 10; // change this number as needed
  const totalPages = Math.ceil(rows.length / rowsPerPage);
  let currentPage = 1;

  function showPage(page) {
    // Clamp page number between 1 and totalPages
    if (page < 1) page = 1;
    if (page > totalPages) page = totalPages;
    currentPage = page;
    rows.forEach((row, index) => {
      row.style.display = (index >= (page - 1) * rowsPerPage && index < page * rowsPerPage) ? "" : "none";
    });
    updatePaginationControls();
  }

  function updatePaginationControls() {
    const container = document.getElementById("pagination-container");
    container.innerHTML = "";

    // "First" button
    const firstBtn = document.createElement("button");
    firstBtn.innerText = "⏮ First";
    firstBtn.className = "px-2 py-1 mx-1 border rounded";
    firstBtn.disabled = currentPage === 1;
    firstBtn.addEventListener("click", () => showPage(1));
    container.appendChild(firstBtn);

    // Previous arrow button
    const prevBtn = document.createElement("button");
    prevBtn.innerText = "←";
    prevBtn.className = "px-2 py-1 mx-1 border rounded";
    prevBtn.disabled = currentPage === 1;
    prevBtn.addEventListener("click", () => showPage(currentPage - 1));
    container.appendChild(prevBtn);

    // Page display text
    const pageDisplay = document.createElement("span");
    pageDisplay.innerText = ` Page ${currentPage} of ${totalPages} `;
    container.appendChild(pageDisplay);

    // Search bar to jump to a specific page
    const pageInput = document.createElement("input");
    pageInput.type = "number";
    pageInput.min = 1;
    pageInput.max = totalPages;
    pageInput.placeholder = "Page #";
    pageInput.style.width = "60px";
    pageInput.className = "mx-1 border p-1 rounded";
    container.appendChild(pageInput);

    // "Go" button to jump to the page entered
    const goBtn = document.createElement("button");
    goBtn.innerText = "Go";
    goBtn.className = "px-2 py-1 mx-1 border rounded";
    goBtn.addEventListener("click", () => {
      const targetPage = parseInt(pageInput.value);
      if (!isNaN(targetPage)) {
        showPage(targetPage);
      }
    });
    container.appendChild(goBtn);

    // Next arrow button
    const nextBtn = document.createElement("button");
    nextBtn.innerText = "→";
    nextBtn.className = "px-2 py-1 mx-1 border rounded";
    nextBtn.disabled = currentPage === totalPages;
    nextBtn.addEventListener("click", () => showPage(currentPage + 1));
    container.appendChild(nextBtn);

    // "Last" button
    const lastBtn = document.createElement("button");
    lastBtn.innerText = "Last ⏭";
    lastBtn.className = "px-2 py-1 mx-1 border rounded";
    lastBtn.disabled = currentPage === totalPages;
    lastBtn.addEventListener("click", () => showPage(totalPages));
    container.appendChild(lastBtn);
  }

  // Create the pagination container if it doesn't exist.
  let paginationContainer = document.getElementById("pagination-container");
  if (!paginationContainer) {
    paginationContainer = document.createElement("div");
    paginationContainer.id = "pagination-container";
    paginationContainer.className = "mt-4 text-center";
    // Insert it after your table wrapper. Adjust the selector as needed.
    const tableDiv = document.querySelector(".overflow-x-auto");
    if (tableDiv) {
      tableDiv.parentNode.insertBefore(paginationContainer, tableDiv.nextSibling);
    } else {
      document.body.appendChild(paginationContainer);
    }
  }

  showPage(1);
});
