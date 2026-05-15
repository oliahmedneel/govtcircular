/* ========================================
   JobSite Hugo Site — Main JavaScript
   ======================================== */

document.addEventListener('DOMContentLoaded', function() {
    initMobileMenu();
    initSearch();
});

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

// Share button copy
function copyPageUrl() {
    navigator.clipboard.writeText(window.location.href)
        .then(() => alert('✅ লিংক কপি করা হয়েছে!'))
        .catch(() => {});
}