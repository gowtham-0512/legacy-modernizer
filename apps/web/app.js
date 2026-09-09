// Modernizer.ai - Alpine.js Application Controller
function modernizerApp() {
    return {
        activeTab: 'modernize',
        backendOnline: false,
        profiles: [],
        selectedProfile: 'fastapi-sqlalchemy',
        profileDescription: 'Python: FastAPI + SQLAlchemy 2.0 (Default)',
        projectName: 'Legacy_Enterprise_App',
        files: [],
        isDragging: false,
        isProcessing: false,
        jobStatus: 'IDLE',
        jobStatusText: 'Ready',
        currentStep: 1,
        progressPercent: 0,
        stageStatusDetail: 'Ready to ingest project artifacts',
        currentJobId: null,
        generatedFiles: [],
        activeFile: null,
        activeFileContent: '',
        copied: false,
        errorMessage: '',
        history: [],
        stageTimer: null,

        async initApp() {
            await this.checkHealth();
            await this.loadProfiles();
            this.refreshIcons();
            this.$watch('activeTab', () => this.refreshIcons());
            this.$watch('jobStatus', () => this.refreshIcons());
            this.$watch('activeFile', () => {
                this.$nextTick(() => {
                    if (window.Prism) Prism.highlightAll();
                    this.refreshIcons();
                });
            });
        },

        refreshIcons() {
            this.$nextTick(() => {
                if (window.lucide) {
                    lucide.createIcons();
                }
            });
        },

        async checkHealth() {
            try {
                const res = await fetch('/api/health');
                this.backendOnline = res.ok;
            } catch (e) {
                this.backendOnline = false;
            }
        },

        async loadProfiles() {
            try {
                const res = await fetch('/api/profiles');
                if (res.ok) {
                    this.profiles = await res.json();
                    if (this.profiles.length > 0) {
                        this.selectedProfile = this.profiles[0].id;
                        this.updateProfileDetails();
                    }
                }
            } catch (e) {
                console.error('Failed to load profiles:', e);
            }
        },

        updateProfileDetails() {
            const p = this.profiles.find(x => x.id === this.selectedProfile);
            if (p) {
                this.profileDescription = `${p.backend} • ${p.database_layer}`;
            }
        },

        handleDrop(e) {
            this.isDragging = false;
            if (e.dataTransfer && e.dataTransfer.files.length > 0) {
                this.addFiles(e.dataTransfer.files);
            }
        },

        handleFileSelect(e) {
            if (e.target.files && e.target.files.length > 0) {
                this.addFiles(e.target.files);
            }
        },

        addFiles(fileList) {
            const arr = Array.from(fileList);
            this.files = this.files.concat(arr);
            this.errorMessage = '';
            this.refreshIcons();
        },

        clearFiles() {
            this.files = [];
            this.errorMessage = '';
            this.refreshIcons();
        },

        formatSize(bytes) {
            if (!bytes || bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
        },

        formatDate(isoStr) {
            if (!isoStr) return '-';
            try {
                const d = new Date(isoStr);
                return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            } catch (e) {
                return isoStr;
            }
        },

        getLanguageClass(filename) {
            if (!filename) return 'python';
            const lower = filename.toLowerCase();
            if (lower.endsWith('.py')) return 'python';
            if (lower.endsWith('.sql')) return 'sql';
            if (lower.endsWith('.json')) return 'json';
            if (lower.endsWith('.java')) return 'java';
            if (lower.endsWith('.md')) return 'markdown';
            if (lower.endsWith('.html')) return 'markup';
            if (lower.endsWith('.css')) return 'css';
            if (lower.endsWith('.js')) return 'javascript';
            return 'python';
        },

        async loadDemoProject() {
            this.projectName = 'Legacy_Java_FullStack';
            this.selectedProfile = 'fastapi-sqlalchemy';
            this.updateProfileDetails();

            const sampleFiles = [
                new File(['package com.legacy.model;\npublic class User { private int id; private String name; }'], 'src/com/legacy/model/User.java', { type: 'text/plain' }),
                new File(['package com.legacy.dao;\nimport java.sql.*;\npublic class UserDAO { public void find() {} }'], 'src/com/legacy/dao/UserDAO.java', { type: 'text/plain' }),
                new File(['CREATE TABLE users (id INT PRIMARY KEY AUTO_INCREMENT, name VARCHAR(100), email VARCHAR(150));'], 'schema.sql', { type: 'text/plain' }),
                new File(['db.url=jdbc:mysql://localhost:3306/company_db\ndb.user=root\ndb.password=secret'], 'application.properties', { type: 'text/plain' }),
                new File(['<html><body><h1>Legacy User Dashboard</h1></body></html>'], 'frontend/index.html', { type: 'text/html' }),
                new File(['console.log("legacy frontend active");'], 'frontend/app.js', { type: 'text/javascript' })
            ];

            this.files = sampleFiles;
            this.errorMessage = '';
            this.refreshIcons();
        },

        async startModernization() {
            if (this.files.length === 0 || this.isProcessing) return;

            this.isProcessing = true;
            this.jobStatus = 'IN_PROGRESS';
            this.jobStatusText = 'Modernizing...';
            this.currentStep = 1;
            this.progressPercent = 15;
            this.stageStatusDetail = 'Ingesting source files into isolated %LOCALAPPDATA% workspace...';
            this.errorMessage = '';
            this.generatedFiles = [];
            this.activeFile = null;
            this.activeFileContent = '';

            const formData = new FormData();
            formData.append('project_name', this.projectName || 'Legacy_Project');
            formData.append('target_stack', this.selectedProfile);

            this.files.forEach(f => {
                const path = f.webkitRelativePath || f.name;
                formData.append('files', f, path);
            });

            let step = 1;
            const stageTexts = [
                'Ingesting source files into isolated %LOCALAPPDATA% workspace...',
                'Agent 1: Extracting business rules, entities & database constraints...',
                'Agent 2: Synthesizing Behavioral Specification Graph (BSG)...',
                'Agent 3: Generating target architecture files & running AST guardrails...',
                'Agent 4: Verifying equivalence & building export package...'
            ];

            this.stageTimer = setInterval(() => {
                if (step < 4) {
                    step++;
                    this.currentStep = step;
                    this.progressPercent = step * 20;
                    this.stageStatusDetail = stageTexts[step - 1];
                    this.refreshIcons();
                }
            }, 6000);

            try {
                const res = await fetch('/api/upload', {
                    method: 'POST',
                    body: formData
                });

                clearInterval(this.stageTimer);

                if (!res.ok) {
                    const err = await res.json().catch(() => ({ detail: 'Modernization request failed.' }));
                    throw new Error(err.detail || 'Server error occurred during modernization.');
                }

                const data = await res.json();
                this.currentJobId = data.job_id;
                this.currentStep = 5;
                this.progressPercent = 100;
                this.jobStatus = 'COMPLETED';
                this.jobStatusText = 'Completed (100%)';
                this.stageStatusDetail = 'All files synthesized, guardrails passed, and ZIP packaged!';

                await this.loadJobFiles(this.currentJobId);

            } catch (e) {
                clearInterval(this.stageTimer);
                this.jobStatus = 'FAILED';
                this.jobStatusText = 'Failed';
                this.errorMessage = e.message || 'Pipeline execution failed.';
                this.stageStatusDetail = 'Modernization pipeline encountered an error.';
            } finally {
                this.isProcessing = false;
                this.refreshIcons();
            }
        },

        async loadJobFiles(jobId) {
            try {
                const res = await fetch(`/api/jobs/${jobId}/files`);
                if (res.ok) {
                    const data = await res.json();
                    this.generatedFiles = data.files || [];
                    if (this.generatedFiles.length > 0) {
                        const defaultFile = this.generatedFiles.find(f => f.includes('main.py') || f.includes('MODERNIZATION_REPORT.md')) || this.generatedFiles[0];
                        await this.selectFile(defaultFile);
                    }
                }
            } catch (e) {
                console.error('Failed to load job files:', e);
            }
        },

        async selectFile(filename) {
            this.activeFile = filename;
            this.activeFileContent = '// Loading file content...';
            try {
                const res = await fetch(`/api/jobs/${this.currentJobId}/file-content?filename=${encodeURIComponent(filename)}`);
                if (res.ok) {
                    const data = await res.json();
                    this.activeFileContent = data.content || '';
                } else {
                    this.activeFileContent = '// Unable to read file content.';
                }
            } catch (e) {
                this.activeFileContent = '// Error reading file from server.';
            }
            this.$nextTick(() => {
                if (window.Prism) Prism.highlightAll();
                this.refreshIcons();
            });
        },

        async copyCode() {
            if (!this.activeFileContent) return;
            try {
                await navigator.clipboard.writeText(this.activeFileContent);
                this.copied = true;
                setTimeout(() => { this.copied = false; }, 2000);
            } catch (e) {
                console.error('Clipboard copy failed:', e);
            }
        },

        async fetchJobHistory() {
            try {
                const res = await fetch('/api/jobs');
                if (res.ok) {
                    this.history = await res.json();
                }
            } catch (e) {
                console.error('Failed to fetch history:', e);
            }
            this.refreshIcons();
        }
    };
}
