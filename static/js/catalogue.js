/**
 * CineBook - Movie Catalogue Filtering & Sorting
 */

document.addEventListener('DOMContentLoaded', () => {
    initCatalogueFilters();
});

function initCatalogueFilters() {
    const searchInput = document.getElementById('movie-search-input');
    const languageSelect = document.getElementById('movie-language-filter');
    const sortSelect = document.getElementById('movie-sort-select');
    const clearBtn = document.getElementById('btn-clear-filters');
    const movieCards = Array.from(document.querySelectorAll('.movie-catalogue-item'));
    const emptyState = document.getElementById('catalogue-empty-state');
    const grid = document.getElementById('movie-catalogue-grid');

    if (!movieCards.length) return;

    function applyFilters() {
        const query = searchInput ? searchInput.value.trim().toLowerCase() : '';
        const selectedLang = languageSelect ? languageSelect.value.trim().toLowerCase() : '';
        const sortBy = sortSelect ? sortSelect.value : 'title_asc';

        let visibleCount = 0;

        // Filter
        movieCards.forEach(card => {
            const title = (card.dataset.title || '').toLowerCase();
            const lang = (card.dataset.language || '').toLowerCase();

            const matchesQuery = !query || title.includes(query);
            const matchesLang = !selectedLang || lang === selectedLang;

            if (matchesQuery && matchesLang) {
                card.style.display = '';
                visibleCount++;
            } else {
                card.style.display = 'none';
            }
        });

        // Sort visible cards
        const sortedCards = movieCards.slice().sort((a, b) => {
            const titleA = a.dataset.title || '';
            const titleB = b.dataset.title || '';
            const durA = parseInt(a.dataset.duration || '0', 10);
            const durB = parseInt(b.dataset.duration || '0', 10);

            if (sortBy === 'title_asc') return titleA.localeCompare(titleB);
            if (sortBy === 'title_desc') return titleB.localeCompare(titleA);
            if (sortBy === 'duration_asc') return durA - durB;
            if (sortBy === 'duration_desc') return durB - durA;
            return 0;
        });

        // Re-append in sorted order
        if (grid) {
            sortedCards.forEach(card => grid.appendChild(card));
        }

        // Empty state visibility
        if (emptyState) {
            emptyState.style.display = (visibleCount === 0) ? 'block' : 'none';
        }
    }

    if (searchInput) {
        searchInput.addEventListener('input', applyFilters);
    }
    if (languageSelect) {
        languageSelect.addEventListener('change', applyFilters);
    }
    if (sortSelect) {
        sortSelect.addEventListener('change', applyFilters);
    }
    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            if (searchInput) searchInput.value = '';
            if (languageSelect) languageSelect.value = '';
            if (sortSelect) sortSelect.value = 'title_asc';
            applyFilters();
        });
    }
}
