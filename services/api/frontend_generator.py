"""Automated Frontend Generator & Sanitizer Engine for Legacy Modernizer V2.

Synthesizes a modern, responsive Single Page Application (SPA) powered by
Tailwind CSS, Alpine.js, and Lucide Icons (zero Node.js/npm dependencies)
tailored to the domain entities and REST API endpoints discovered in the project.
Also sanitizes and upgrades preserved legacy frontends.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional


def extract_entity_metadata(files_dict: Dict[str, str]) -> Dict[str, Any]:
    """
    Extracts primary domain entity, fields, types, and endpoints from generated backend files.
    """
    entity_name = "Item"
    entity_plural = "items"
    fields: List[Dict[str, Any]] = []

    # Strategy 1: Inspect schemas.py (Pydantic models)
    schemas_content = files_dict.get("schemas.py", "")
    if not schemas_content:
        for k, v in files_dict.items():
            if k.endswith("schemas.py"):
                schemas_content = v
                break

    if schemas_content:
        # Look for class <Entity>Base(BaseModel):
        base_match = re.search(r"class\s+([A-Za-z0-9_]+)Base\s*\(\s*BaseModel\s*\)\s*:\s*\n((?:\s+[A-Za-z0-9_]+\s*:\s*.*?\n)+)", schemas_content)
        if not base_match:
            base_match = re.search(r"class\s+([A-Za-z0-9_]+)\s*\(\s*BaseModel\s*\)\s*:\s*\n((?:\s+[A-Za-z0-9_]+\s*:\s*.*?\n)+)", schemas_content)

        if base_match:
            entity_name = base_match.group(1)
            raw_body = base_match.group(2)
            for line in raw_body.strip().splitlines():
                line = line.strip()
                if ":" in line and not line.startswith("def ") and not line.startswith("class ") and not line.startswith("@"):
                    parts = line.split(":", 1)
                    fname = parts[0].strip()
                    ftype_raw = parts[1].split("=")[0].strip().lower()
                    if fname.startswith("_") or fname == "id":
                        continue
                    
                    if "int" in ftype_raw:
                        itype = "number"
                        step = "1"
                    elif "float" in ftype_raw:
                        itype = "number"
                        step = "any"
                    elif "bool" in ftype_raw:
                        itype = "checkbox"
                        step = None
                    elif "email" in fname.lower() or "mail" in fname.lower():
                        itype = "email"
                        step = None
                    elif "date" in fname.lower() or "time" in fname.lower():
                        itype = "date"
                        step = None
                    else:
                        itype = "text"
                        step = None
                    
                    fields.append({
                        "name": fname,
                        "label": fname.replace("_", " ").title(),
                        "type": itype,
                        "step": step,
                        "required": "optional" not in ftype_raw
                    })

    # Strategy 2: Fallback to models.py if schemas.py was empty
    if not fields:
        models_content = files_dict.get("models.py", "")
        class_match = re.search(r"class\s+([A-Za-z0-9_]+)\s*\(\s*(?:Base|DeclarativeBase)\s*\)\s*:\s*\n((?:\s+[A-Za-z0-9_]+\s*=\s*.*?\n)+)", models_content)
        if class_match:
            entity_name = class_match.group(1)
            raw_body = class_match.group(2)
            for line in raw_body.strip().splitlines():
                line = line.strip()
                if "=" in line and not line.startswith("def "):
                    fname = line.split("=")[0].strip()
                    if fname.startswith("_") or fname == "id" or fname == "__tablename__":
                        continue
                    fields.append({
                        "name": fname,
                        "label": fname.replace("_", " ").title(),
                        "type": "text",
                        "step": None,
                        "required": True
                    })

    # Default fallback
    if not fields:
        entity_name = "Record"
        fields = [
            {"name": "name", "label": "Name", "type": "text", "step": None, "required": True},
            {"name": "department", "label": "Department", "type": "text", "step": None, "required": True},
            {"name": "email", "label": "Email", "type": "email", "step": None, "required": False},
        ]

    # Calculate plural
    entity_plural = entity_name.lower() + "s"
    if entity_plural.endswith("ys"):
        entity_plural = entity_plural[:-2] + "ies"

    # Check main.py for registered endpoints
    main_content = files_dict.get("main.py", "")
    endpoints = re.findall(r'["\']/api/([a-zA-Z0-9_\-]+)["\']', main_content)
    for ep in endpoints:
        if ep not in ("health", "stats", "docs", "openapi.json"):
            entity_plural = ep
            break

    return {
        "entity_name": entity_name,
        "entity_plural": entity_plural,
        "api_endpoint": f"/api/{entity_plural}",
        "fields": fields
    }


def generate_modern_spa(meta: Dict[str, Any]) -> Dict[str, str]:
    """
    Generates a complete modern Tailwind + Alpine.js SPA (index.html, app.js, style.css).
    """
    entity = meta["entity_name"]
    endpoint = meta["api_endpoint"]
    fields = meta["fields"]

    th_tags = "".join([f'<th class="px-4 py-3 text-left text-xs font-semibold text-slate-300 uppercase tracking-wider">{f["label"]}</th>\n' for f in fields])
    td_tags = "".join([f'<td class="px-4 py-3 text-sm text-slate-200" x-text="item.{f["name"]} !== undefined && item.{f["name"]} !== null ? item.{f["name"]} : \'-\'"></td>\n' for f in fields])

    form_inputs = []
    default_form_fields = []
    for f in fields:
        req_attr = 'required' if f['required'] else ''
        step_attr = f'step="{f["step"]}"' if f['step'] else ''
        form_inputs.append(
            f'<div>\n'
            f'    <label class="block text-xs font-medium text-slate-300 mb-1.5">{f["label"]}</label>\n'
            f'    <input type="{f["type"]}" {step_attr} {req_attr} x-model="formData.{f["name"]}"\n'
            f'           placeholder="Enter {f["label"].lower()}..."\n'
            f'           class="w-full px-3.5 py-2.5 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition">\n'
            f'</div>'
        )
        default_form_fields.append(f'"{f["name"]}": ""')

    form_inputs_html = "\n".join(form_inputs)
    default_form_str = "{\n" + ",\n".join([f'                {df}' for df in default_form_fields]) + "\n            }"
    search_conditions = " || ".join([f'(item.{f["name"]} && String(item.{f["name"]}).toLowerCase().includes(q))' for f in fields])

    index_html = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{entity} Management System | Modernized</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🚀</text></svg>">
    
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {{
            darkMode: 'class',
            theme: {{
                extend: {{
                    fontFamily: {{
                        sans: ['"Plus Jakarta Sans"', 'system-ui', 'sans-serif'],
                        mono: ['"JetBrains Mono"', 'monospace'],
                    }},
                    colors: {{
                        dark: {{
                            base: '#0b0f19',
                            surface: '#111827',
                            card: '#1f2937',
                            border: '#374151',
                        }},
                        brand: {{
                            500: '#6366f1',
                            600: '#4f46e5',
                        }}
                    }}
                }}
            }}
        }}
    </script>
    
    <script src="https://unpkg.com/lucide@latest"></script>
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
    <link rel="stylesheet" href="style.css">
</head>
<body class="bg-dark-base text-slate-100 min-h-screen font-sans antialiased" x-data="entityApp()" x-init="init()">

    <div class="fixed top-5 right-5 z-50 space-y-2">
        <template x-if="toast.visible">
            <div :class="toast.type === 'error' ? 'bg-rose-500/90 border-rose-600' : 'bg-emerald-500/90 border-emerald-600'"
                 class="px-4 py-3 rounded-xl border text-white text-sm shadow-xl flex items-center gap-3 transition-all duration-300">
                <span x-text="toast.message"></span>
                <button @click="toast.visible = false" class="text-white/80 hover:text-white">&times;</button>
            </div>
        </template>
    </div>

    <header class="bg-dark-surface/80 backdrop-blur-md border-b border-dark-border sticky top-0 z-30">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
            <div class="flex items-center gap-3">
                <div class="w-9 h-9 rounded-xl bg-gradient-to-tr from-brand-600 to-indigo-500 flex items-center justify-center text-white shadow-lg">
                    <i data-lucide="layers" class="w-5 h-5"></i>
                </div>
                <div>
                    <h1 class="text-base font-bold tracking-tight text-white">{entity} Management</h1>
                    <p class="text-[11px] text-slate-400 font-medium">Modern REST Architecture • FastAPI</p>
                </div>
            </div>

            <div class="flex items-center gap-2">
                <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold"
                      :class="healthOnline ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'">
                    <span class="w-2 h-2 rounded-full" :class="healthOnline ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'"></span>
                    <span x-text="healthOnline ? 'API Online' : 'API Connecting...'"></span>
                </span>
                <a href="/docs" target="_blank" class="text-xs px-3 py-1 rounded-lg bg-dark-card hover:bg-slate-700 text-slate-300 border border-dark-border transition flex items-center gap-1.5">
                    <i data-lucide="external-link" class="w-3.5 h-3.5"></i>
                    <span>Swagger API</span>
                </a>
            </div>
        </div>
    </header>

    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-5 mb-8">
            <div class="bg-dark-surface p-5 rounded-2xl border border-dark-border shadow-sm">
                <p class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Total {entity}s</p>
                <div class="flex items-baseline justify-between">
                    <h3 class="text-3xl font-extrabold text-white" x-text="items.length">0</h3>
                    <span class="text-xs font-medium text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">Active</span>
                </div>
            </div>

            <div class="bg-dark-surface p-5 rounded-2xl border border-dark-border shadow-sm">
                <p class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Backend Target</p>
                <div class="flex items-baseline justify-between">
                    <h3 class="text-xl font-bold text-white">FastAPI + SQL</h3>
                    <span class="text-xs font-medium text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded">Async REST</span>
                </div>
            </div>

            <div class="bg-dark-surface p-5 rounded-2xl border border-dark-border shadow-sm">
                <p class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Modern Frontend</p>
                <div class="flex items-baseline justify-between">
                    <h3 class="text-xl font-bold text-white">Tailwind + Alpine</h3>
                    <span class="text-xs font-medium text-cyan-400 bg-cyan-500/10 px-2 py-0.5 rounded">Zero npm</span>
                </div>
            </div>
        </div>

        <div class="flex flex-col sm:flex-row items-center justify-between gap-4 mb-6">
            <div class="relative w-full sm:w-96">
                <i data-lucide="search" class="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2"></i>
                <input type="text" x-model="searchQuery" placeholder="Search {entity.lower()}s..."
                       class="w-full pl-10 pr-4 py-2.5 rounded-xl bg-dark-surface border border-dark-border text-white text-sm focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 transition shadow-sm">
            </div>

            <button @click="openCreateModal()"
                    class="w-full sm:w-auto px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-sm shadow-lg shadow-indigo-600/20 transition flex items-center justify-center gap-2">
                <i data-lucide="plus" class="w-4 h-4"></i>
                <span>Add {entity}</span>
            </button>
        </div>

        <div class="bg-dark-surface rounded-2xl border border-dark-border overflow-hidden shadow-xl">
            <div class="overflow-x-auto">
                <table class="w-full border-collapse text-left">
                    <thead>
                        <tr class="bg-slate-900/60 border-b border-dark-border">
                            <th class="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider"># ID</th>
                            {th_tags}
                            <th class="px-4 py-3 text-right text-xs font-semibold text-slate-400 uppercase tracking-wider">Actions</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-dark-border">
                        <template x-for="item in filteredItems" :key="item.id">
                            <tr class="hover:bg-slate-800/40 transition">
                                <td class="px-4 py-3 text-xs font-mono text-slate-400" x-text="item.id"></td>
                                {td_tags}
                                <td class="px-4 py-3 text-right text-sm space-x-2 whitespace-nowrap">
                                    <button @click="openEditModal(item)" class="p-1.5 rounded-lg text-slate-400 hover:text-indigo-400 hover:bg-slate-800 transition" title="Edit">
                                        <i data-lucide="edit-3" class="w-4 h-4"></i>
                                    </button>
                                    <button @click="deleteItem(item.id)" class="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-slate-800 transition" title="Delete">
                                        <i data-lucide="trash-2" class="w-4 h-4"></i>
                                    </button>
                                </td>
                            </tr>
                        </template>

                        <tr x-show="filteredItems.length === 0 && !isLoading">
                            <td colspan="{len(fields) + 2}" class="px-4 py-12 text-center text-slate-400">
                                <div class="flex flex-col items-center justify-center gap-2">
                                    <i data-lucide="inbox" class="w-8 h-8 text-slate-500"></i>
                                    <p class="text-sm font-medium">No {entity.lower()} records found.</p>
                                    <p class="text-xs text-slate-500">Click "Add {entity}" above to create your first record.</p>
                                </div>
                            </td>
                        </tr>

                        <tr x-show="isLoading">
                            <td colspan="{len(fields) + 2}" class="px-4 py-12 text-center text-slate-400">
                                <div class="flex items-center justify-center gap-2">
                                    <div class="w-5 h-5 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
                                    <span class="text-sm">Fetching {entity.lower()}s from API...</span>
                                </div>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </main>

    <div x-show="modalOpen" x-transition.opacity class="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
        <div @click.away="modalOpen = false" class="bg-slate-900 border border-slate-700 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-5">
            <div class="flex items-center justify-between border-b border-slate-800 pb-4">
                <h3 class="text-base font-bold text-white" x-text="modalMode === 'create' ? 'Add New {entity}' : 'Edit {entity}'"></h3>
                <button @click="modalOpen = false" class="text-slate-400 hover:text-white">&times;</button>
            </div>

            <form @submit.prevent="saveItem()" class="space-y-4">
                {form_inputs_html}

                <div class="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
                    <button type="button" @click="modalOpen = false" class="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-medium transition">
                        Cancel
                    </button>
                    <button type="submit" class="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold shadow-lg shadow-indigo-600/20 transition">
                        Save {entity}
                    </button>
                </div>
            </form>
        </div>
    </div>

    <script src="app.js"></script>
</body>
</html>
"""

    app_js = f"""// Modernizer REST Client Controller for {entity}
function entityApp() {{
    return {{
        items: [],
        isLoading: false,
        searchQuery: '',
        modalOpen: false,
        modalMode: 'create',
        editId: null,
        healthOnline: false,
        formData: {default_form_str},
        toast: {{ visible: false, message: '', type: 'success' }},

        async init() {{
            await this.checkHealth();
            await this.fetchItems();
            this.refreshIcons();
        }},

        refreshIcons() {{
            this.$nextTick(() => {{
                if (window.lucide) lucide.createIcons();
            }});
        }},

        showToast(message, type = 'success') {{
            this.toast = {{ visible: true, message, type }};
            setTimeout(() => {{ this.toast.visible = false; }}, 4000);
        }},

        async checkHealth() {{
            try {{
                const res = await fetch('/api/health');
                this.healthOnline = res.ok;
            }} catch (e) {{
                this.healthOnline = false;
            }}
        }},

        async fetchItems() {{
            this.isLoading = true;
            try {{
                const res = await fetch('{endpoint}');
                if (res.ok) {{
                    this.items = await res.json();
                }} else {{
                    this.showToast('Failed to load {entity.lower()}s from server', 'error');
                }}
            }} catch (e) {{
                this.showToast('Network error connecting to API', 'error');
            }} finally {{
                this.isLoading = false;
                this.refreshIcons();
            }}
        }},

        get filteredItems() {{
            if (!this.searchQuery.trim()) return this.items;
            const q = this.searchQuery.toLowerCase();
            return this.items.filter(item => {search_conditions});
        }},

        openCreateModal() {{
            this.modalMode = 'create';
            this.editId = null;
            this.formData = {default_form_str};
            this.modalOpen = true;
            this.refreshIcons();
        }},

        openEditModal(item) {{
            this.modalMode = 'edit';
            this.editId = item.id;
            this.formData = Object.assign({{}}, item);
            this.modalOpen = true;
            this.refreshIcons();
        }},

        async saveItem() {{
            const isEdit = this.modalMode === 'edit';
            const url = isEdit ? `{endpoint}/${{this.editId}}` : '{endpoint}';
            const method = isEdit ? 'PUT' : 'POST';

            const payload = Object.assign({{}}, this.formData);
            delete payload.id;

            try {{
                const res = await fetch(url, {{
                    method: method,
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify(payload)
                }});

                if (res.ok) {{
                    this.showToast(`{entity} ${{isEdit ? 'updated' : 'created'}} successfully!`);
                    this.modalOpen = false;
                    await this.fetchItems();
                }} else {{
                    const err = await res.json().catch(() => ({{ detail: 'Operation failed' }}));
                    this.showToast(err.detail || 'Validation error saving record', 'error');
                }}
            }} catch (e) {{
                this.showToast('Network error saving {entity.lower()}', 'error');
            }}
        }},

        async deleteItem(id) {{
            if (!confirm(`Are you sure you want to delete this {entity.lower()}?`)) return;

            try {{
                const res = await fetch(`{endpoint}/${{id}}`, {{
                    method: 'DELETE'
                }});

                if (res.ok) {{
                    this.showToast('{entity} deleted successfully!');
                    await this.fetchItems();
                }} else {{
                    this.showToast('Failed to delete {entity.lower()}', 'error');
                }}
            }} catch (e) {{
                this.showToast('Network error deleting record', 'error');
            }}
        }}
    }};
}}
"""

    style_css = """/* Custom Modern UI Tweaks */
::-webkit-scrollbar {
    width: 6px;
    height: 6px;
}

::-webkit-scrollbar-track {
    background: #0b0f19;
}

::-webkit-scrollbar-thumb {
    background: #1f2937;
    border-radius: 9999px;
}

::-webkit-scrollbar-thumb:hover {
    background: #374151;
}
"""

    return {
        "frontend/index.html": index_html,
        "frontend/app.js": app_js,
        "frontend/style.css": style_css,
        "static/index.html": index_html,
        "static/app.js": app_js,
        "static/style.css": style_css
    }


def sanitize_legacy_frontend(frontend_dir: Path) -> int:
    """
    Sanitizes legacy HTML and JS files:
    1. Replaces restrictive input number steps with step="any".
    2. Rewrites hardcoded localhost URLs to relative /api endpoints.
    """
    modified_count = 0
    for hfile in frontend_dir.glob("**/*.html"):
        try:
            content = hfile.read_text(encoding="utf-8")
            orig = content
            content = re.sub(r'min=["\']1["\']\s+step=["\']\d+["\']', 'min="0" step="any"', content)
            content = re.sub(r'step=["\']\d+["\']', 'step="any"', content)
            if content != orig:
                hfile.write_text(content, encoding="utf-8")
                modified_count += 1
        except Exception:
            pass

    for jsfile in frontend_dir.glob("**/*.js"):
        try:
            content = jsfile.read_text(encoding="utf-8")
            orig = content
            content = re.sub(r'https?://localhost:\d+/api/', '/api/', content)
            if content != orig:
                jsfile.write_text(content, encoding="utf-8")
                modified_count += 1
        except Exception:
            pass

    return modified_count