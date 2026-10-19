/**
 * CineBook - Main Core Script (Enhanced with BookMyShow & IMDb Features)
 * Provides global navigation, modal handlers, toast notifications,
 * header quick search auto-suggest, trailer video modal, and watchlist syncing.
 */

document.addEventListener('DOMContentLoaded', () => {
    initNavToggle();
    initModals();
    initScrollAnimations();
    initGlobalToasts();
    initQuickSearch();
    initWatchlistButtons();
    initStarRatingPickers();
});

// Mobile Navigation Toggle
function initNavToggle() {
    const toggleBtn = document.querySelector('.nav-toggle-btn');
    const navLinks = document.querySelector('.nav-links');
    if (toggleBtn && navLinks) {
        toggleBtn.addEventListener('click', () => {
            navLinks.classList.toggle('show');
            const isExpanded = navLinks.classList.contains('show');
            toggleBtn.setAttribute('aria-expanded', isExpanded);
        });

        document.addEventListener('click', (e) => {
            if (!toggleBtn.contains(e.target) && !navLinks.contains(e.target)) {
                navLinks.classList.remove('show');
            }
        });
    }
}

// Global Toast System
function showToast(message, type = 'info', duration = 4000) {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    if (type === 'error') icon = '⚠️';
    if (type === 'warning') icon = '🔔';

    toast.innerHTML = `
        <span class="toast-icon">${icon}</span>
        <div class="toast-body">${message}</div>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('toast-closing');
        setTimeout(() => toast.remove(), 250);
    }, duration);
}

function initGlobalToasts() {
    const flashMessages = document.querySelectorAll('.flash-message-data');
    flashMessages.forEach(el => {
        const msg = el.dataset.message;
        const category = el.dataset.category || 'info';
        if (msg) {
            showToast(msg, category === 'danger' ? 'error' : category);
        }
    });
}

// Modal Handlers
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = '';
        // If trailer modal, stop video playback
        const iframe = modal.querySelector('iframe');
        if (iframe) {
            iframe.src = '';
        }
    }
}

function initModals() {
    document.addEventListener('click', (e) => {
        if (e.target.classList.contains('modal-overlay')) {
            const modal = e.target;
            closeModal(modal.id);
        }
        if (e.target.closest('.modal-close-btn')) {
            const modal = e.target.closest('.modal-overlay');
            if (modal) {
                closeModal(modal.id);
            }
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const activeModal = document.querySelector('.modal-overlay.active');
            if (activeModal) {
                closeModal(activeModal.id);
            }
        }
    });
}

// Trailer Video Modal
function playTrailer(embedUrl, movieTitle) {
    let modal = document.getElementById('global-trailer-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'global-trailer-modal';
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal-dialog" style="max-width: 820px; background: #000; padding: 0;">
                <div class="card-header" style="background: rgba(14, 19, 34, 0.95); border-bottom: 1px solid var(--border-subtle); padding: 0.85rem 1.25rem;">
                    <h3 id="trailer-modal-title" style="margin: 0; font-size: 1.15rem; color: #fff;">Official Trailer</h3>
                    <button type="button" class="modal-close-btn" onclick="closeModal('global-trailer-modal')">×</button>
                </div>
                <div class="video-responsive-wrap">
                    <iframe id="trailer-iframe" src="" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }

    const titleEl = modal.querySelector('#trailer-modal-title');
    const iframe = modal.querySelector('#trailer-iframe');
    if (titleEl) titleEl.textContent = `${movieTitle} — Official Trailer`;
    if (iframe) iframe.src = embedUrl;

    openModal('global-trailer-modal');
}

// Global Header Quick Search (IMDb style autocomplete)
function initQuickSearch() {
    const input = document.getElementById('header-quick-search');
    const popover = document.getElementById('quick-search-popover');
    if (!input || !popover) return;

    let debounceTimer = null;

    input.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        const query = input.value.trim();
        if (query.length < 2) {
            popover.classList.remove('active');
            popover.innerHTML = '';
            return;
        }

        debounceTimer = setTimeout(async () => {
            try {
                const res = await fetch(`/api/movies/quick-search?q=${encodeURIComponent(query)}`);
                if (res.ok) {
                    const results = await res.json();
                    renderQuickSearchResults(results, popover);
                }
            } catch (err) {
                console.error('Quick search error:', err);
            }
        }, 220);
    });

    document.addEventListener('click', (e) => {
        if (!input.contains(e.target) && !popover.contains(e.target)) {
            popover.classList.remove('active');
        }
    });
}

function renderQuickSearchResults(results, popover) {
    if (!results || results.length === 0) {
        popover.innerHTML = `
            <div style="padding: 1.25rem; text-align: center; color: var(--text-muted); font-size: 0.88rem;">
                No movies found. <a href="/movies" style="color: var(--accent-primary); text-decoration: underline;">Browse Catalogue</a>
            </div>
        `;
        popover.classList.add('active');
        return;
    }

    let html = '';
    results.forEach(m => {
        html += `
            <a href="${m.url}" class="quick-search-item">
                <img src="${m.poster_url}" class="quick-search-thumb" alt="${m.title}" onerror="this.src='https://placehold.co/40x56/161c30/f59e0b?text=CB'">
                <div>
                    <div style="font-weight: 700; font-size: 0.92rem; color: var(--text-primary);">${m.title}</div>
                    <div style="font-size: 0.78rem; color: var(--text-muted);">
                        <span>${m.language}</span> • <span>${m.duration || ''}</span> • <span style="color: #fbbf24;">★ ${m.rating}</span>
                    </div>
                </div>
            </a>
        `;
    });

    popover.innerHTML = html;
    popover.classList.add('active');
}

// Watchlist Toggle Handlers
function initWatchlistButtons() {
    document.addEventListener('click', async (e) => {
        const btn = e.target.closest('.btn-watchlist');
        if (!btn) return;

        const movieId = btn.dataset.movieId;
        if (!movieId) return;

        btn.disabled = true;
        try {
            const res = await fetch('/api/watchlist/toggle', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ movie_id: movieId })
            });

            if (res.ok) {
                const data = await res.json();
                const inWatchlist = data.in_watchlist;

                btn.classList.toggle('in-watchlist', inWatchlist);
                btn.innerHTML = inWatchlist ? '✓ In Watchlist' : '+ Add to Watchlist';

                // Update navbar badge if present
                const badge = document.getElementById('nav-watchlist-count');
                if (badge) {
                    badge.textContent = data.count;
                    badge.style.display = data.count > 0 ? 'inline-flex' : 'none';
                }

                showToast(data.message, inWatchlist ? 'success' : 'info');
            }
        } catch (err) {
            console.error('Watchlist error:', err);
            showToast('Unable to update watchlist right now.', 'error');
        } finally {
            btn.disabled = false;
        }
    });
}

// 1-10 Star Rating Pickers for User Reviews
function initStarRatingPickers() {
    const pickers = document.querySelectorAll('.star-rating-picker');
    pickers.forEach(picker => {
        const input = document.getElementById(picker.dataset.targetInput);
        const valueDisplay = document.getElementById(picker.dataset.targetDisplay);
        const stars = picker.querySelectorAll('.star');

        stars.forEach(star => {
            star.addEventListener('mouseenter', () => {
                const val = parseInt(star.dataset.val, 10);
                stars.forEach(s => {
                    const sVal = parseInt(s.dataset.val, 10);
                    s.classList.toggle('hovered', sVal <= val);
                });
                if (valueDisplay) valueDisplay.textContent = `${val}/10`;
            });

            star.addEventListener('click', () => {
                const val = parseInt(star.dataset.val, 10);
                if (input) input.value = val;
                stars.forEach(s => {
                    const sVal = parseInt(s.dataset.val, 10);
                    s.classList.toggle('selected', sVal <= val);
                });
                if (valueDisplay) valueDisplay.textContent = `${val}/10 Stars Selected`;
            });
        });

        picker.addEventListener('mouseleave', () => {
            stars.forEach(s => s.classList.remove('hovered'));
            const currentVal = input ? parseInt(input.value || '0', 10) : 0;
            if (valueDisplay) {
                valueDisplay.textContent = currentVal > 0 ? `${currentVal}/10 Stars Selected` : 'Rate from 1 to 10 stars';
            }
        });
    });
}

// Review Submission Handler
async function submitReview(movieId) {
    const nameInput = document.getElementById('review-user-name');
    const ratingInput = document.getElementById('review-rating-val');
    const textInput = document.getElementById('review-text-content');
    const submitBtn = document.getElementById('btn-submit-review');

    const name = nameInput ? nameInput.value.trim() : 'Anonymous';
    const rating = ratingInput ? parseInt(ratingInput.value, 10) : 0;
    const text = textInput ? textInput.value.trim() : '';

    if (!rating || rating < 1 || rating > 10) {
        showToast('Please select a star rating between 1 and 10.', 'error');
        return;
    }
    if (!text || text.length < 5) {
        showToast('Please share at least a short sentence for your review.', 'error');
        return;
    }

    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Posting Review...';
    }

    try {
        const res = await fetch(`/api/reviews/${movieId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_name: name,
                rating: rating,
                review_text: text
            })
        });

        const data = await res.json();
        if (res.ok) {
            showToast('Review posted successfully! Thank you.', 'success');
            closeModal('review-modal');
            setTimeout(() => window.location.reload(), 600);
        } else {
            showToast(data.error || 'Failed to submit review.', 'error');
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.textContent = 'Submit Review';
            }
        }
    } catch (err) {
        console.error('Submit review error:', err);
        showToast('Network error while posting review.', 'error');
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Submit Review';
        }
    }
}

// Format Currency helper
function formatCurrency(num) {
    return '₹' + parseFloat(num || 0).toLocaleString('en-IN', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

// Intersection Observer for Entrance Transitions
function initScrollAnimations() {
    if ('IntersectionObserver' in window) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.1 });

        document.querySelectorAll('.animate-on-scroll').forEach(el => {
            observer.observe(el);
        });
    }
}
