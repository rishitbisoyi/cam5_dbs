/**
 * CineBook - Admin Dashboard JavaScript
 * Handles CRUD modal popups, deletion confirmations, and Chart.js reporting visualizations.
 */

document.addEventListener('DOMContentLoaded', () => {
    initAdminSidebarToggle();
    initConfirmDeletes();
    initAnalyticsCharts();
});

// Admin Mobile Sidebar Toggle
function initAdminSidebarToggle() {
    const toggleBtn = document.getElementById('admin-sidebar-toggle');
    const sidebar = document.querySelector('.admin-sidebar');
    if (toggleBtn && sidebar) {
        toggleBtn.addEventListener('click', () => {
            sidebar.classList.toggle('show');
        });
    }
}

// Confirmation modal before destructive delete actions
function initConfirmDeletes() {
    document.querySelectorAll('.btn-delete-confirm').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const entityName = btn.dataset.entity || 'item';
            const msg = `Are you sure you want to delete this ${entityName}? If it is referenced by existing bookings or schedules, deletion will be safely rejected by the database.`;
            if (!confirm(msg)) {
                e.preventDefault();
            }
        });
    });
}

// Chart.js Visualizations for Analytics
async function initAnalyticsCharts() {
    const revenueCanvas = document.getElementById('chart-revenue-breakdown');
    const movieBookingsCanvas = document.getElementById('chart-movie-bookings');
    const theatreDistCanvas = document.getElementById('chart-theatre-distribution');
    const snacksCanvas = document.getElementById('chart-snacks-sales');
    const trendsCanvas = document.getElementById('chart-daily-trends');

    if (!revenueCanvas && !movieBookingsCanvas && !theatreDistCanvas && !snacksCanvas && !trendsCanvas) {
        return;
    }

    try {
        const res = await fetch('/api/admin/analytics-data');
        if (!res.ok) throw new Error('Failed to fetch analytics metrics');
        const data = await res.json();

        // 1. Revenue Breakdown (Doughnut)
        if (revenueCanvas) {
            new Chart(revenueCanvas, {
                type: 'doughnut',
                data: {
                    labels: ['Ticket Revenue', 'Snack Revenue'],
                    datasets: [{
                        data: [data.ticket_revenue, data.snack_revenue],
                        backgroundColor: ['#f59e0b', '#06b6d4'],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'bottom', labels: { color: '#94a3b8' } }
                    }
                }
            });
        }

        // 2. Bookings by Movie (Bar)
        if (movieBookingsCanvas) {
            new Chart(movieBookingsCanvas, {
                type: 'bar',
                data: {
                    labels: data.movies.map(m => m.name),
                    datasets: [{
                        label: 'Tickets Sold',
                        data: data.movies.map(m => m.tickets),
                        backgroundColor: '#f59e0b',
                        borderRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { ticks: { color: '#94a3b8' }, grid: { display: false } },
                        y: { ticks: { color: '#94a3b8', stepSize: 1 }, grid: { color: 'rgba(255,255,255,0.06)' } }
                    },
                    plugins: {
                        legend: { display: false }
                    }
                }
            });
        }

        // 3. Bookings by Theatre (PolarArea or Pie)
        if (theatreDistCanvas) {
            new Chart(theatreDistCanvas, {
                type: 'polarArea',
                data: {
                    labels: data.theatres.map(t => t.name),
                    datasets: [{
                        data: data.theatres.map(t => t.bookings),
                        backgroundColor: ['#f59e0b', '#06b6d4', '#10b981', '#6366f1']
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'bottom', labels: { color: '#94a3b8' } }
                    },
                    scales: {
                        r: { grid: { color: 'rgba(255,255,255,0.08)' } }
                    }
                }
            });
        }

        // 4. Snack Sales (Bar)
        if (snacksCanvas) {
            new Chart(snacksCanvas, {
                type: 'bar',
                data: {
                    labels: data.snacks.map(s => s.name),
                    datasets: [{
                        label: 'Units Sold',
                        data: data.snacks.map(s => s.sold_quantity),
                        backgroundColor: '#06b6d4',
                        borderRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { ticks: { color: '#94a3b8' }, grid: { display: false } },
                        y: { ticks: { color: '#94a3b8', stepSize: 1 }, grid: { color: 'rgba(255,255,255,0.06)' } }
                    },
                    plugins: {
                        legend: { display: false }
                    }
                }
            });
        }

        // 5. Daily Trends (Line)
        if (trendsCanvas) {
            new Chart(trendsCanvas, {
                type: 'line',
                data: {
                    labels: data.daily_trends.map(d => d.date),
                    datasets: [{
                        label: 'Daily Revenue (₹)',
                        data: data.daily_trends.map(d => d.revenue),
                        borderColor: '#f59e0b',
                        backgroundColor: 'rgba(245, 158, 11, 0.15)',
                        fill: true,
                        tension: 0.35,
                        pointBackgroundColor: '#fbbf24'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { ticks: { color: '#94a3b8' }, grid: { display: false } },
                        y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.06)' } }
                    },
                    plugins: {
                        legend: { labels: { color: '#94a3b8' } }
                    }
                }
            });
        }

    } catch (err) {
        console.error('Error rendering analytics charts:', err);
    }
}
