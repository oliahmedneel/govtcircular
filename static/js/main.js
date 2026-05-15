/* ========================================
   JobSite — Main JavaScript (Unified)
   ======================================== */

document.addEventListener('DOMContentLoaded', function() {
    // Determine if we are on Dashboard or Hugo Site
    const isDashboard = document.querySelector('.sidebar') !== null;

    if (isDashboard) {
        initDashboard();
    } else {
        initHugoSite();
    }
});

/* ========================================
   HUGO SITE LOGIC
   ======================================== */
function initHugoSite() {
    initMobileMenu();
    initSearch();
}

function initMobileMenu() {
    const toggle = document.getElementById('menuToggle');
    const menu = document.getElementById('mobileMenu');
    if (!toggle || !menu) return;

    toggle.addEventListener('click', function() {
        menu.classList.toggle('hidden');
    });

    // Close when clicking a link
    menu.querySelectorAll('a').forEach(link => {
        link.addEventListener('click', () => menu.classList.add('hidden'));
    });
}

function initSearch() {
    const searchInput = document.getElementById('searchInput');
    const searchResults = document.getElementById('searchResults');
    if (!searchInput || !searchResults) return;

    let searchIndex = [];

    // Load search index
    fetch('/search-index.json')
        .then(r => r.json())
        .then(data => {
            searchIndex = data;
        })
        .catch(() => {});

    let debounceTimer;

    searchInput.addEventListener('input', function() {
        clearTimeout(debounceTimer);
        const query = this.value.trim().toLowerCase();
        
        if (query.length < 2) {
            searchResults.classList.add('hidden');
            return;
        }

        debounceTimer = setTimeout(() => {
            const results = searchIndex.filter(post =>
                post.title.toLowerCase().includes(query) ||
                post.summary.toLowerCase().includes(query) ||
                post.tags.some(tag => tag.toLowerCase().includes(query))
            ).slice(0, 10);

            if (results.length === 0) {
                searchResults.innerHTML = '<div class="p-3 text-sm text-gray-500">কোনো ফলাফল পাওয়া যায়নি</div>';
            } else {
                searchResults.innerHTML = results.map(post => `
                    <a href="${post.url}" class="block p-3 border-b border-gray-100 hover:bg-gray-50 transition">
                        <div class="text-sm font-medium text-gray-900">${post.title}</div>
                        <div class="text-xs text-gray-500 mt-0.5">${post.category_bn}</div>
                    </a>
                `).join('');
            }
            searchResults.classList.remove('hidden');
        }, 300);
    });

    // Close on click outside
    document.addEventListener('click', function(e) {
        if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
            searchResults.classList.add('hidden');
        }
    });
}

/* ========================================
   DASHBOARD LOGIC
   ======================================== */
function initDashboard() {
    initSidebar();
    initTheme();
    initToasts();
    
    // Auto-load common data if on specific pages
    if (document.getElementById('systemInfo')) loadSystemInfo('systemInfo');
    if (document.getElementById('dbRecordsContainer')) loadDbRecords();
}

function initSidebar() {
    const toggle = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');
    const mobileToggle = document.getElementById('mobileSidebarToggle');

    if (toggle && sidebar) {
        toggle.addEventListener('click', () => {
            sidebar.classList.toggle('collapsed');
            const icon = toggle.querySelector('i');
            if (sidebar.classList.contains('collapsed')) {
                icon.className = 'bi bi-chevron-right';
            } else {
                icon.className = 'bi bi-chevron-left';
            }
        });
    }

    if (mobileToggle && sidebar) {
        mobileToggle.addEventListener('click', () => {
            sidebar.classList.toggle('mobile-show');
        });
    }
}

function initTheme() {
    const toggle = document.getElementById('themeToggle');
    if (!toggle) return;

    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-bs-theme', savedTheme);
    updateThemeIcon(savedTheme);

    toggle.addEventListener('click', () => {
        const current = document.documentElement.getAttribute('data-bs-theme');
        const next = current === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-bs-theme', next);
        localStorage.setItem('theme', next);
        updateThemeIcon(next);
    });
}

function updateThemeIcon(theme) {
    const toggle = document.getElementById('themeToggle');
    if (!toggle) return;
    const icon = toggle.querySelector('i');
    if (theme === 'dark') {
        icon.className = 'bi bi-sun';
    } else {
        icon.className = 'bi bi-moon-stars';
    }
}

function initToasts() {
    const toastEl = document.getElementById('liveToast');
    if (toastEl) {
        window.showToast = (message, title = 'JobSite') => {
            const toast = new bootstrap.Toast(toastEl);
            toastEl.querySelector('.toast-body').textContent = message;
            toastEl.querySelector('strong').textContent = title;
            toast.show();
        };
    }
}

/* Dashboard Actions */
function loadSystemInfo(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    fetch('/api/system-info')
        .then(r => r.json())
        .then(data => {
            container.innerHTML = `
                <div class="space-y-2">
                    <div class="d-flex justify-content-between">
                        <span class="text-muted small">AI মডেল:</span>
                        <span class="badge bg-light text-dark">${data.config_summary.ai_model}</span>
                    </div>
                    <div class="d-flex justify-content-between">
                        <span class="text-muted small">OCR ভাষা:</span>
                        <span class="badge bg-light text-dark">${data.config_summary.ocr_languages}</span>
                    </div>
                    <div class="d-flex justify-content-between">
                        <span class="text-muted small">Auto Push:</span>
                        <span class="badge ${data.config_summary.auto_push ? 'bg-success' : 'bg-secondary'}">${data.config_summary.auto_push ? 'চালু' : 'বন্ধ'}</span>
                    </div>
                    <div class="d-flex justify-content-between">
                        <span class="text-muted small">ডাটাবেস:</span>
                        <span class="small">${data.db_stats.total_posts} পোস্ট</span>
                    </div>
                </div>
            `;
        })
        .catch(() => {
            container.innerHTML = '<p class="text-danger small">তথ্য লোড করা যায়নি</p>';
        });
}

function runSetup() {
    if (!confirm('আপনি কি নিশ্চিত যে সিস্টেম সেটআপ পুনরায় রান করতে চান?')) return;
    
    showOverlay(true, 'সেটআপ হচ্ছে...');
    fetch('/api/run-setup', { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            showOverlay(false);
            if (data.success) {
                alert('✅ ' + data.message);
                location.reload();
            } else {
                alert('❌ ' + data.error);
            }
        });
}

function quickGitPush() {
    const msg = prompt('Git কমিট মেসেজ দিন:', 'Manual deploy from dashboard');
    if (msg === null) return;

    showOverlay(true, 'Git Push হচ্ছে...');
    fetch('/api/git-push', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg })
    })
    .then(r => r.json())
    .then(data => {
        showOverlay(false);
        if (data.success) {
            alert('✅ ' + data.message);
        } else {
            alert('❌ ' + data.error);
        }
    });
}

function processFile(filename) {
    showOverlay(true, 'ফাইল প্রসেস করা হচ্ছে: ' + filename);
    fetch('/api/run-pipeline', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filepath: filename })
    })
    .then(r => r.json())
    .then(data => {
        showOverlay(false);
        if (data.success) {
            alert('✅ সফলভাবে প্রসেস করা হয়েছে: ' + data.slug);
            location.reload();
        } else {
            alert('❌ ত্রুটি: ' + data.error);
        }
    })
    .catch(err => {
        showOverlay(false);
        alert('❌ Error: ' + err.message);
    });
}

function deleteFile(filename, folder) {
    if (!confirm('আপনি কি এই ফাইলটি মুছে ফেলতে চান?')) return;
    
    fetch('/api/delete-file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: filename, folder: folder })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) location.reload();
        else alert('❌ ' + data.error);
    });
}

function clearFolder(folder, callback) {
    if (!confirm(`আপনি কি ${folder} ফোল্ডারের সব ফাইল মুছে ফেলতে চান?`)) return;
    
    fetch('/api/clear-folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder: folder })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            if (callback) callback();
            else location.reload();
        } else alert('❌ ' + data.error);
    });
}

function moveToUploads(filename, source) {
    fetch('/api/move-to-uploads', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filepath: filename, source: source })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) location.reload();
        else alert('❌ ' + data.error);
    });
}

function loadDbRecords() {
    const container = document.getElementById('dbRecordsContainer');
    if (!container) return;

    fetch('/api/db-records')
        .then(r => r.json())
        .then(data => {
            let html = `
                <div class="table-responsive">
                    <table class="table table-hover mb-0">
                        <thead class="table-light">
                            <tr>
                                <th>ফাইল</th>
                                <th>ক্যাটাগরি</th>
                                <th>স্লাগ</th>
                                <th>স্ট্যাটাস</th>
                                <th>সময়</th>
                            </tr>
                        </thead>
                        <tbody>
            `;
            
            if (data.files && data.files.length > 0) {
                data.files.forEach(f => {
                    const statusClass = f.status === 'success' ? 'bg-success' : (f.status === 'failed' ? 'bg-danger' : 'bg-warning');
                    html += `
                        <tr>
                            <td><small class="fw-medium">${f.filename}</small></td>
                            <td><span class="badge bg-info">${f.category || 'N/A'}</span></td>
                            <td><code>${f.slug || 'N/A'}</code></td>
                            <td><span class="badge ${statusClass}">${f.status}</span></td>
                            <td><small class="text-muted">${f.processed_at || f.created_at}</small></td>
                        </tr>
                    `;
                });
            } else {
                html += '<tr><td colspan="5" class="text-center py-4">কোনো রেকর্ড পাওয়া যায়নি</td></tr>';
            }
            
            html += '</tbody></table></div>';
            container.innerHTML = html;
        });
}

function uploadMultipleFiles(files) {
    const status = document.getElementById('multiUploadStatus');
    if (status) {
        status.className = 'mt-2 small alert alert-info';
        status.textContent = `⏳ ${files.length} টি ফাইল আপলোড হচ্ছে...`;
        status.classList.remove('d-none');
    }

    const promises = Array.from(files).map(file => {
        const formData = new FormData();
        formData.append('file', file);
        return fetch('/upload-json', { method: 'POST', body: formData }).then(r => r.json());
    });

    Promise.all(promises)
        .then(results => {
            const successCount = results.filter(r => r.success).length;
            if (status) {
                status.className = 'mt-2 small alert alert-success';
                status.textContent = `✅ ${successCount}/${files.length} টি ফাইল আপলোড করা হয়েছে। রিফ্রেশ হচ্ছে...`;
            }
            setTimeout(() => location.reload(), 2000);
        })
        .catch(err => {
            if (status) {
                status.className = 'mt-2 small alert alert-danger';
                status.textContent = '❌ Error: ' + err.message;
            }
        });
}

function clearDatabase(callback) {
    if (!confirm('আপনি কি ডাটাবেস এর সব রেকর্ড মুছে ফেলতে চান? এটি পোস্টগুলো ডিলিট করবে না।')) return;
    
    fetch('/api/db-clear', { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                if (callback) callback();
                else location.reload();
            } else alert('❌ ' + data.error);
        });
}

function showOverlay(show, text = 'প্রসেসিং হচ্ছে...') {
    const overlay = document.getElementById('loadingOverlay');
    if (!overlay) return;
    
    if (show) {
        overlay.querySelector('p').textContent = text;
        overlay.classList.remove('d-none');
    } else {
        overlay.classList.add('d-none');
    }
}

/* Utilities */
function copyPageUrl() {
    navigator.clipboard.writeText(window.location.href)
        .then(() => {
            if (window.showToast) showToast('লিংক কপি করা হয়েছে!');
            else alert('✅ লিংক কপি করা হয়েছে!');
        })
        .catch(() => {});
}