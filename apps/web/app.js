// Legacy Modernizer V2 Client Application

document.addEventListener("DOMContentLoaded", () => {
    // State
    let selectedFiles = [];
    let currentJobId = null;
    let targetProfiles = [];

    // DOM Elements
    const backendStatusDot = document.getElementById("backendStatusDot");
    const backendStatusText = document.getElementById("backendStatusText");
    const targetStackSelect = document.getElementById("targetStackSelect");
    const targetStackHint = document.getElementById("targetStackHint");
    const dropZone = document.getElementById("dropZone");
    const fileInput = document.getElementById("fileInput");
    const folderInput = document.getElementById("folderInput");
    const fileSummary = document.getElementById("fileSummary");
    const fileCountText = document.getElementById("fileCountText");
    const clearFilesBtn = document.getElementById("clearFilesBtn");
    const startModernizationBtn = document.getElementById("startModernizationBtn");
    const projectNameInput = document.getElementById("projectName");

    // Stepper & Progress Elements
    const jobStatusBadge = document.getElementById("jobStatusBadge");
    const progressFill = document.getElementById("progressFill");
    const progressLabel = document.getElementById("progressLabel");
    const pipelineErrorAlert = document.getElementById("pipelineErrorAlert");
    const pipelineErrorMsg = document.getElementById("pipelineErrorMsg");

    // Results Elements
    const resultsCard = document.getElementById("resultsCard");
    const resultsSubtitle = document.getElementById("resultsSubtitle");
    const downloadZipBtn = document.getElementById("downloadZipBtn");
    const generatedFileList = document.getElementById("generatedFileList");
    const codeViewer = document.getElementById("codeViewer");
    const activeFilename = document.getElementById("activeFilename");
    const copyCodeBtn = document.getElementById("copyCodeBtn");

    // Tab Navigation
    const navItems = document.querySelectorAll(".nav-item");
    const tabPanes = document.querySelectorAll(".tab-pane");
    const refreshHistoryBtn = document.getElementById("refreshHistoryBtn");
    const historyTableBody = document.getElementById("historyTableBody");

    // -------------------------------------------------------------
    // 1. Initialize & Check Backend Health
    // -------------------------------------------------------------
    async function initApp() {
        try {
            const healthRes = await fetch("/api/health");
            if (healthRes.ok) {
                const health = await healthRes.json();
                backendStatusDot.className = "status-indicator online";
                backendStatusText.textContent = "API Online (Isolated Storage)";
            } else {
                throw new Error("Backend offline");
            }
        } catch (e) {
            backendStatusDot.className = "status-indicator offline";
            backendStatusText.textContent = "Backend Disconnected";
        }

        // Fetch Target Profiles
        try {
            const profRes = await fetch("/api/profiles");
            if (profRes.ok) {
                targetProfiles = await profRes.json();
                targetStackSelect.innerHTML = targetProfiles.map(p => 
                    `<option value="${p.id}">${p.name}</option>`
                ).join("");
                updateProfileHint();
            }
        } catch (e) {
            console.error("Could not fetch target profiles:", e);
        }
    }

    function updateProfileHint() {
        const selected = targetProfiles.find(p => p.id === targetStackSelect.value);
        if (selected) {
            targetStackHint.textContent = `${selected.backend} | ${selected.database_layer}`;
        }
    }

    targetStackSelect.addEventListener("change", updateProfileHint);

    // -------------------------------------------------------------
    // 2. Tab Switching
    // -------------------------------------------------------------
    navItems.forEach(item => {
        item.addEventListener("click", () => {
            navItems.forEach(n => n.classList.remove("active"));
            tabPanes.forEach(p => p.classList.remove("active"));

            item.classList.add("active");
            const targetId = item.getAttribute("data-tab") + "Tab";
            const targetPane = document.getElementById(targetId);
            if (targetPane) targetPane.classList.add("active");

            if (item.getAttribute("data-tab") === "history") {
                loadJobHistory();
            }
        });
    });

    // -------------------------------------------------------------
    // 3. File Selection & Drag-and-Drop
    // -------------------------------------------------------------
    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("dragover");
    });

    dropZone.addEventListener("dragleave", () => {
        dropZone.classList.remove("dragover");
    });

    dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.classList.remove("dragover");
        if (e.dataTransfer.files.length > 0) {
            handleFiles(e.dataTransfer.files);
        }
    });

    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) handleFiles(e.target.files);
    });

    folderInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) handleFiles(e.target.files);
    });

    function handleFiles(files) {
        selectedFiles = Array.from(files);
        fileCountText.textContent = `${selectedFiles.length} file(s) selected`;
        fileSummary.style.display = "flex";
        startModernizationBtn.disabled = selectedFiles.length === 0;
    }

    clearFilesBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        selectedFiles = [];
        fileInput.value = "";
        folderInput.value = "";
        fileSummary.style.display = "none";
        startModernizationBtn.disabled = true;
    });

    // -------------------------------------------------------------
    // 4. Start Modernization
    // -------------------------------------------------------------
    startModernizationBtn.addEventListener("click", async () => {
        if (selectedFiles.length === 0) return;

        startModernizationBtn.disabled = true;
        pipelineErrorAlert.style.display = "none";
        resultsCard.style.display = "none";

        updateStepper(1, "IN_PROGRESS");
        setProgress(15);

        const formData = new FormData();
        formData.append("project_name", projectNameInput.value.trim() || "legacy_project");
        formData.append("target_stack", targetStackSelect.value);

        selectedFiles.forEach(file => {
            // Use webkitRelativePath if folder upload, else file.name
            const path = file.webkitRelativePath || file.name;
            formData.append("files", file, path);
        });

        // Stage progress animation timer while waiting for AI pipeline
        let currentStep = 1;
        const stageInterval = setInterval(() => {
            if (currentStep < 4) {
                currentStep++;
                updateStepper(currentStep, "IN_PROGRESS");
                setProgress(currentStep * 20);
            }
        }, 5000);

        try {
            const response = await fetch("/api/upload", {
                method: "POST",
                body: formData
            });

            clearInterval(stageInterval);

            if (!response.ok) {
                const errData = await response.json().catch(() => ({ detail: "Modernization failed." }));
                throw new Error(errData.detail || "Server error occurred during modernization.");
            }

            const result = await response.json();
            currentJobId = result.job_id;

            // Mark complete
            updateStepper(5, "COMPLETED");
            setProgress(100);

            // Fetch job file list and display
            await loadJobResults(currentJobId);

        } catch (err) {
            clearInterval(stageInterval);
            updateStepper(currentStep, "FAILED");
            pipelineErrorAlert.style.display = "block";
            pipelineErrorMsg.textContent = err.message;
        } finally {
            startModernizationBtn.disabled = false;
        }
    });

    function setProgress(percent) {
        progressFill.style.width = `${percent}%`;
        progressLabel.textContent = `${percent}%`;
    }

    function updateStepper(activeStepIndex, status) {
        for (let i = 1; i <= 5; i++) {
            const stepEl = document.getElementById(`step${i}`);
            stepEl.classList.remove("active", "completed");
            if (i < activeStepIndex) {
                stepEl.classList.add("completed");
            } else if (i === activeStepIndex) {
                stepEl.classList.add("active");
                if (status === "COMPLETED") stepEl.classList.add("completed");
            }
        }

        jobStatusBadge.className = `badge badge-${status.toLowerCase()}`;
        jobStatusBadge.textContent = status;
    }

    // -------------------------------------------------------------
    // 5. Load Results & Interactive Code Preview
    // -------------------------------------------------------------
    async function loadJobResults(jobId) {
        resultsCard.style.display = "block";
        resultsSubtitle.textContent = `Job Workspace ID: ${jobId} (Isolated in %LOCALAPPDATA%)`;
        downloadZipBtn.href = `/api/jobs/${jobId}/download`;

        try {
            const filesRes = await fetch(`/api/jobs/${jobId}/files`);
            if (!filesRes.ok) throw new Error("Could not fetch generated files.");
            const data = await filesRes.json();

            generatedFileList.innerHTML = data.files.map(fname => `
                <li class="file-item" data-filename="${fname}">
                    ${getFileIcon(fname)} ${fname}
                </li>
            `).join("");

            // Setup click handlers for files
            const items = generatedFileList.querySelectorAll(".file-item");
            items.forEach(item => {
                item.addEventListener("click", () => {
                    items.forEach(i => i.classList.remove("active"));
                    item.classList.add("active");
                    previewFileContent(jobId, item.getAttribute("data-filename"));
                });
            });

            // Auto-preview first file
            if (items.length > 0) {
                items[0].click();
            }

        } catch (e) {
            console.error("Could not load job files:", e);
        }
    }

    async function previewFileContent(jobId, filename) {
        activeFilename.textContent = filename;
        codeViewer.textContent = "Loading file content...";
        try {
            const res = await fetch(`/api/jobs/${jobId}/file-content?filename=${encodeURIComponent(filename)}`);
            if (res.ok) {
                const data = await res.json();
                codeViewer.textContent = data.content;
            } else {
                codeViewer.textContent = "// Could not load file content.";
            }
        } catch (e) {
            codeViewer.textContent = `// Error reading file: ${e.message}`;
        }
    }

    function getFileIcon(filename) {
        if (filename.endsWith(".py")) return "🐍";
        if (filename.endsWith(".java")) return "☕";
        if (filename.endsWith(".sql")) return "🗄️";
        if (filename.endsWith(".json")) return "📋";
        if (filename.endsWith(".md")) return "📝";
        if (filename.endsWith(".bat")) return "⚙️";
        return "📄";
    }

    copyCodeBtn.addEventListener("click", () => {
        navigator.clipboard.writeText(codeViewer.textContent).then(() => {
            copyCodeBtn.textContent = "Copied!";
            setTimeout(() => { copyCodeBtn.textContent = "Copy"; }, 2000);
        });
    });

    // -------------------------------------------------------------
    // 6. Job History Tab
    // -------------------------------------------------------------
    async function loadJobHistory() {
        historyTableBody.innerHTML = `<tr><td colspan="7" class="text-center">Loading history...</td></tr>`;
        try {
            const res = await fetch("/api/jobs");
            if (!res.ok) throw new Error("Could not load jobs.");
            const jobs = await res.json();

            if (jobs.length === 0) {
                historyTableBody.innerHTML = `<tr><td colspan="7" class="text-center">No jobs found. Modernize a project to see runs here.</td></tr>`;
                return;
            }

            historyTableBody.innerHTML = jobs.map(j => `
                <tr>
                    <td><code>${j.job_id}</code></td>
                    <td><strong>${j.project_name}</strong></td>
                    <td><span class="badge badge-idle">${j.target_stack}</span></td>
                    <td><span class="badge badge-${j.status.toLowerCase()}">${j.status}</span></td>
                    <td>${j.total_files}</td>
                    <td>${new Date(j.created_at).toLocaleString()}</td>
                    <td>
                        ${j.status === "COMPLETED" 
                            ? `<a href="/api/jobs/${j.job_id}/download" class="btn btn-secondary" style="padding: 4px 8px; font-size: 0.75rem;">Download ZIP</a>` 
                            : `<span class="text-secondary">-</span>`
                        }
                    </td>
                </tr>
            `).join("");

        } catch (e) {
            historyTableBody.innerHTML = `<tr><td colspan="7" class="text-center text-danger">Error loading history: ${e.message}</td></tr>`;
        }
    }

    refreshHistoryBtn.addEventListener("click", loadJobHistory);

    // Initial run
    initApp();
});
