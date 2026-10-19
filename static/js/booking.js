/**
 * CineBook - Interactive Multi-Step Booking Engine (BookMyShow-inspired UX)
 * Handles show loading, dynamic seat map rendering, 10-minute seat locking timer,
 * persistent desktop summary, mobile sticky bar, customer auto-lookup, snacks computation,
 * demo payment simulation, and atomic transaction booking submission.
 */

const BookingApp = {
    currentStep: 1,
    selectedShowId: null,
    showData: null,
    bookedSeats: new Set(),
    selectedSeats: new Map(), // seatNo -> price
    snacks: new Map(), // snackId -> { name, price, qty }
    customer: { name: '', phone: '' },
    paymentMode: 'UPI',
    timerInterval: null,
    timerSeconds: 600, // 10 minutes holding window

    // Seat tier pricing rule consistent with database sample tickets
    getSeatPrice(seatNo) {
        const row = seatNo.charAt(0).toUpperCase();
        if (row === 'A') return 120.00; // Standard Front Row
        if (row === 'B' || row === 'C') return 150.00; // Executive Middle
        return 180.00; // VIP Recliner Rows (D, E, F...)
    },

    getSeatTierName(seatNo) {
        const row = seatNo.charAt(0).toUpperCase();
        if (row === 'A') return 'Standard (₹120)';
        if (row === 'B' || row === 'C') return 'Executive (₹150)';
        return 'VIP Recliner (₹180)';
    },

    init() {
        const params = new URLSearchParams(window.location.search);
        const showIdParam = params.get('show_id');

        this.bindEvents();

        if (showIdParam) {
            this.selectedShowId = parseInt(showIdParam, 10);
            this.loadShowDetails(this.selectedShowId);
        } else {
            this.goToStep(1);
        }
    },

    bindEvents() {
        // Step navigation buttons
        document.querySelectorAll('[data-goto-step]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const targetStep = parseInt(e.currentTarget.dataset.gotoStep, 10);
                if (this.validateStep(this.currentStep, targetStep)) {
                    this.goToStep(targetStep);
                }
            });
        });

        // Show selector dropdown (if on Step 1)
        const showSelect = document.getElementById('show-selector');
        if (showSelect) {
            showSelect.addEventListener('change', (e) => {
                if (e.target.value) {
                    this.selectedShowId = parseInt(e.target.value, 10);
                    this.loadShowDetails(this.selectedShowId);
                }
            });
        }

        // Phone lookup auto-fill
        const phoneInput = document.getElementById('customer-phone');
        if (phoneInput) {
            phoneInput.addEventListener('input', (e) => {
                const phone = e.target.value.trim();
                if (phone.length === 10) {
                    this.lookupCustomerPhone(phone);
                }
            });
        }

        // Payment mode selection
        document.querySelectorAll('input[name="payment_mode"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                this.paymentMode = e.target.value;
                this.updatePaymentSimulationView();
            });
        });

        // Booking submission
        const submitBtn = document.getElementById('btn-confirm-booking');
        if (submitBtn) {
            submitBtn.addEventListener('click', () => this.submitBooking());
        }

        // Concessions category filter pills
        document.querySelectorAll('.snack-cat-pill').forEach(pill => {
            pill.addEventListener('click', (e) => {
                document.querySelectorAll('.snack-cat-pill').forEach(p => p.classList.remove('active'));
                pill.classList.add('active');
                const cat = pill.dataset.category;
                document.querySelectorAll('.snack-card').forEach(card => {
                    if (cat === 'all' || card.dataset.category === cat) {
                        card.style.display = 'flex';
                    } else {
                        card.style.display = 'none';
                    }
                });
            });
        });
    },

    startReservationTimer(durationSeconds = 600) {
        clearInterval(this.timerInterval);
        this.timerSeconds = durationSeconds;

        const updateDisplay = () => {
            const minutes = Math.floor(this.timerSeconds / 60);
            const seconds = this.timerSeconds % 60;
            const formatted = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;

            document.querySelectorAll('.countdown-timer-val').forEach(el => {
                el.textContent = formatted;
            });

            if (this.timerSeconds <= 0) {
                clearInterval(this.timerInterval);
                showToast('Seat holding window has expired. Refreshing seat availability.', 'warning');
                this.selectedSeats.clear();
                if (this.selectedShowId) {
                    this.loadShowDetails(this.selectedShowId);
                }
            } else {
                this.timerSeconds--;
            }
        };

        updateDisplay();
        this.timerInterval = setInterval(updateDisplay, 1000);
    },

    goToStep(stepNumber) {
        this.currentStep = stepNumber;

        // Update stepper indicators
        document.querySelectorAll('.step-node').forEach(node => {
            const step = parseInt(node.dataset.step, 10);
            node.classList.remove('active', 'completed');
            if (step === stepNumber) {
                node.classList.add('active');
            } else if (step < stepNumber) {
                node.classList.add('completed');
            }
        });

        // Update step view panels
        document.querySelectorAll('.booking-step-panel').forEach(panel => {
            panel.style.display = 'none';
        });

        const activePanel = document.getElementById(`step-panel-${stepNumber}`);
        if (activePanel) {
            activePanel.style.display = 'block';
            window.scrollTo({ top: activePanel.offsetTop - 100, behavior: 'smooth' });
        }

        // Start countdown timer when in seat selection or later
        if (stepNumber >= 2 && !this.timerInterval) {
            this.startReservationTimer(600);
        }

        this.updateOrderSummary();
        this.updatePersistentSummary();
    },

    validateStep(fromStep, toStep) {
        if (toStep < fromStep) return true; // Allowed to go back

        if (fromStep === 1) {
            if (!this.selectedShowId) {
                showToast('Please select a movie showtime to continue.', 'error');
                return false;
            }
        }

        if (fromStep === 2) {
            if (this.selectedSeats.size === 0) {
                showToast('Please select at least one seat to continue.', 'error');
                return false;
            }
        }

        if (fromStep === 3) {
            const name = document.getElementById('customer-name')?.value.trim();
            const phone = document.getElementById('customer-phone')?.value.trim();

            if (!name || name.length < 2) {
                showToast('Please enter a valid customer name.', 'error');
                return false;
            }
            if (!phone || !/^\d{10}$/.test(phone)) {
                showToast('Please enter a valid 10-digit phone number.', 'error');
                return false;
            }
            this.customer.name = name;
            this.customer.phone = phone;
        }

        return true;
    },

    async loadShowDetails(showId) {
        try {
            const res = await fetch(`/api/shows/${showId}/details`);
            if (!res.ok) throw new Error('Show details not found');
            const data = await res.json();
            this.showData = data;

            // Update booked seats Set
            this.bookedSeats = new Set(data.booked_seats || []);

            // Render show header banner
            this.renderShowHeader(data);

            // Render interactive seat grid
            this.renderSeatGrid(data.capacity || 100);

            // Move to step 2 (Seat selection)
            this.goToStep(2);
        } catch (err) {
            showToast('Unable to load show details. Please try another show.', 'error');
            console.error(err);
        }
    },

    renderShowHeader(data) {
        const titleEl = document.getElementById('booking-movie-title');
        const metaEl = document.getElementById('booking-show-meta');
        if (titleEl) titleEl.textContent = data.movie_name;
        if (metaEl) {
            metaEl.innerHTML = `
                <span>🏛️ ${data.theatre_name} (Screen ${data.screen_no})</span> • 
                <span>📅 ${data.formatted_date}</span> • 
                <span>⏰ ${data.formatted_time}</span> • 
                <span>🗣️ ${data.language} (${data.formatted_duration || data.duration + 'm'})</span>
            `;
        }

        // Update persistent sidebar header info
        const sideMovie = document.getElementById('side-summary-movie');
        const sideTheatre = document.getElementById('side-summary-theatre');
        const sideDatetime = document.getElementById('side-summary-datetime');
        if (sideMovie) sideMovie.textContent = data.movie_name;
        if (sideTheatre) sideTheatre.textContent = `${data.theatre_name} (Screen ${data.screen_no})`;
        if (sideDatetime) sideDatetime.textContent = `${data.formatted_date} • ${data.formatted_time}`;
    },

    renderSeatGrid(capacity) {
        const container = document.getElementById('seat-grid-container');
        if (!container) return;
        container.innerHTML = '';

        // Generate rows A through F based on capacity (10 seats per row)
        const seatsPerRow = 10;
        const numRows = Math.min(Math.ceil(capacity / seatsPerRow), 10);
        const rowLetters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'J', 'K'];

        for (let r = 0; r < numRows; r++) {
            const rowLetter = rowLetters[r];
            const rowDiv = document.createElement('div');
            rowDiv.className = 'seat-row';

            // Row letter on left
            const leftLabel = document.createElement('div');
            leftLabel.className = 'seat-row-label';
            leftLabel.textContent = rowLetter;
            rowDiv.appendChild(leftLabel);

            for (let c = 1; c <= seatsPerRow; c++) {
                // Aisle gap in middle
                if (c === 6) {
                    const gap = document.createElement('div');
                    gap.className = 'seat-aisle-gap';
                    rowDiv.appendChild(gap);
                }

                const seatNo = `${rowLetter}${c}`;
                const seatBtn = document.createElement('div');
                seatBtn.className = 'seat-item';
                seatBtn.textContent = c;
                seatBtn.dataset.seat = seatNo;
                seatBtn.title = `Seat ${seatNo} - ${this.getSeatTierName(seatNo)}`;

                if (this.bookedSeats.has(seatNo)) {
                    seatBtn.classList.add('booked');
                    seatBtn.title = `Seat ${seatNo} (Already Booked)`;
                } else {
                    if (this.selectedSeats.has(seatNo)) {
                        seatBtn.classList.add('selected');
                    }

                    seatBtn.addEventListener('click', () => this.toggleSeat(seatNo, seatBtn));
                }

                rowDiv.appendChild(seatBtn);
            }

            // Row letter on right
            const rightLabel = document.createElement('div');
            rightLabel.className = 'seat-row-label';
            rightLabel.textContent = rowLetter;
            rowDiv.appendChild(rightLabel);

            container.appendChild(rowDiv);
        }

        this.updateSeatSelectionBar();
        this.updatePersistentSummary();
    },

    toggleSeat(seatNo, seatBtn) {
        if (this.bookedSeats.has(seatNo)) return;

        if (this.selectedSeats.has(seatNo)) {
            this.selectedSeats.delete(seatNo);
            seatBtn.classList.remove('selected');
        } else {
            if (this.selectedSeats.size >= 8) {
                showToast('You can select a maximum of 8 seats per booking.', 'warning');
                return;
            }
            const price = this.getSeatPrice(seatNo);
            this.selectedSeats.set(seatNo, price);
            seatBtn.classList.add('selected');
        }

        this.updateSeatSelectionBar();
        this.updatePersistentSummary();
    },

    updateSeatSelectionBar() {
        const countEl = document.getElementById('selected-seats-count');
        const listEl = document.getElementById('selected-seats-list');
        const subtotalEl = document.getElementById('selected-seats-subtotal');
        const proceedBtn = document.getElementById('btn-proceed-to-customer');

        const seatsArr = Array.from(this.selectedSeats.keys());
        let subtotal = 0;
        this.selectedSeats.forEach(price => subtotal += price);

        if (countEl) countEl.textContent = seatsArr.length;
        if (listEl) listEl.textContent = seatsArr.length > 0 ? seatsArr.join(', ') : 'None selected';
        if (subtotalEl) subtotalEl.textContent = formatCurrency(subtotal);

        if (proceedBtn) {
            proceedBtn.disabled = (seatsArr.length === 0);
        }
    },

    updatePersistentSummary() {
        const sideSeats = document.getElementById('side-summary-seats');
        const sideTicketsTotal = document.getElementById('side-summary-tickets-total');
        const sideSnacksTotal = document.getElementById('side-summary-snacks-total');
        const sideGrandTotal = document.getElementById('side-summary-grand-total');

        const mobileSeats = document.getElementById('mobile-summary-seats');
        const mobileTotal = document.getElementById('mobile-summary-total');
        const mobileBtn = document.getElementById('mobile-btn-continue');

        let ticketTotal = 0;
        this.selectedSeats.forEach(p => ticketTotal += p);

        let snackTotal = 0;
        this.snacks.forEach(s => snackTotal += s.qty * s.price);

        const grandTotal = ticketTotal + snackTotal;
        const seatsArr = Array.from(this.selectedSeats.keys());

        if (sideSeats) sideSeats.textContent = seatsArr.length > 0 ? seatsArr.join(', ') : 'No seats chosen';
        if (sideTicketsTotal) sideTicketsTotal.textContent = formatCurrency(ticketTotal);
        if (sideSnacksTotal) sideSnacksTotal.textContent = formatCurrency(snackTotal);
        if (sideGrandTotal) sideGrandTotal.textContent = formatCurrency(grandTotal);

        if (mobileSeats) mobileSeats.textContent = `${seatsArr.length} Seat(s)`;
        if (mobileTotal) mobileTotal.textContent = formatCurrency(grandTotal);
        if (mobileBtn) mobileBtn.disabled = (seatsArr.length === 0);
    },

    async lookupCustomerPhone(phone) {
        try {
            const res = await fetch(`/api/customer/lookup?phone=${encodeURIComponent(phone)}`);
            if (res.ok) {
                const data = await res.json();
                if (data.exists && data.customer_name) {
                    const nameInput = document.getElementById('customer-name');
                    if (nameInput && !nameInput.value) {
                        nameInput.value = data.customer_name;
                        showToast(`Welcome back, ${data.customer_name}!`, 'info');
                    }
                }
            }
        } catch (err) {
            console.error('Customer lookup error:', err);
        }
    },

    changeSnackQty(snackId, delta, price, name) {
        const current = this.snacks.get(snackId) || { name, price, qty: 0 };
        const newQty = Math.max(0, current.qty + delta);

        if (newQty === 0) {
            this.snacks.delete(snackId);
        } else {
            this.snacks.set(snackId, { name, price, qty: newQty });
        }

        const qtyEl = document.getElementById(`snack-qty-${snackId}`);
        if (qtyEl) qtyEl.textContent = newQty;

        this.updateSnacksSubtotal();
        this.updatePersistentSummary();
    },

    updateSnacksSubtotal() {
        let snackTotal = 0;
        this.snacks.forEach(s => {
            snackTotal += s.qty * s.price;
        });

        const subtotalEl = document.getElementById('snacks-subtotal');
        if (subtotalEl) subtotalEl.textContent = formatCurrency(snackTotal);
    },

    updatePaymentSimulationView() {
        document.querySelectorAll('.payment-tab-content').forEach(el => el.style.display = 'none');
        const activeTab = document.getElementById(`payment-tab-${this.paymentMode.toLowerCase()}`);
        if (activeTab) activeTab.style.display = 'block';
    },

    updateOrderSummary() {
        let ticketTotal = 0;
        this.selectedSeats.forEach(p => ticketTotal += p);

        let snackTotal = 0;
        this.snacks.forEach(s => snackTotal += s.qty * s.price);

        const grandTotal = ticketTotal + snackTotal;

        const reviewMovie = document.getElementById('review-movie');
        const reviewTheatre = document.getElementById('review-theatre');
        const reviewDatetime = document.getElementById('review-datetime');
        const reviewSeats = document.getElementById('review-seats');
        const reviewCustomer = document.getElementById('review-customer');
        const reviewTicketTotal = document.getElementById('review-ticket-subtotal');
        const reviewSnackTotal = document.getElementById('review-snack-subtotal');
        const reviewGrandTotal = document.getElementById('review-grand-total');

        if (this.showData) {
            if (reviewMovie) reviewMovie.textContent = this.showData.movie_name;
            if (reviewTheatre) reviewTheatre.textContent = `${this.showData.theatre_name} (Screen ${this.showData.screen_no})`;
            if (reviewDatetime) reviewDatetime.textContent = `${this.showData.formatted_date} at ${this.showData.formatted_time}`;
        }

        if (reviewSeats) reviewSeats.textContent = Array.from(this.selectedSeats.keys()).join(', ');
        if (reviewCustomer) reviewCustomer.textContent = `${this.customer.name} (${this.customer.phone})`;
        if (reviewTicketTotal) reviewTicketTotal.textContent = formatCurrency(ticketTotal);
        if (reviewSnackTotal) reviewSnackTotal.textContent = formatCurrency(snackTotal);
        if (reviewGrandTotal) reviewGrandTotal.textContent = formatCurrency(grandTotal);

        const snacksListEl = document.getElementById('review-snacks-list');
        if (snacksListEl) {
            if (this.snacks.size === 0) {
                snacksListEl.innerHTML = '<span class="text-muted">No snacks selected</span>';
            } else {
                let html = '<ul style="list-style:none; padding:0; margin:0;">';
                this.snacks.forEach((s) => {
                    html += `<li style="display:flex; justify-content:space-between; margin-bottom:4px;">
                        <span>${s.name} × ${s.qty}</span>
                        <span>${formatCurrency(s.qty * s.price)}</span>
                    </li>`;
                });
                html += '</ul>';
                snacksListEl.innerHTML = html;
            }
        }
    },

    async submitBooking() {
        const submitBtn = document.getElementById('btn-confirm-booking');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = `
                <span class="spinner" style="display:inline-block; width:16px; height:16px; border:2px solid #000; border-top-color:transparent; border-radius:50%; animation:spin 0.6s linear infinite; margin-right:8px;"></span>
                Securing Seats in CineBookDB...
            `;
        }

        const payload = {
            show_id: this.selectedShowId,
            seats: Array.from(this.selectedSeats.keys()),
            customer_name: this.customer.name,
            customer_phone: this.customer.phone,
            payment_mode: this.paymentMode,
            snacks: {}
        };

        this.snacks.forEach((item, id) => {
            if (item.qty > 0) {
                payload.snacks[id] = item.qty;
            }
        });

        try {
            const res = await fetch('/api/booking/submit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await res.json();

            if (!res.ok) {
                if (res.status === 409) {
                    showToast(data.message || 'Seat conflict: One or more selected seats were just taken. Please choose another.', 'error', 6000);
                    await this.loadShowDetails(this.selectedShowId);
                    this.goToStep(2);
                } else {
                    showToast(data.message || 'Booking submission failed. Please try again.', 'error');
                }
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Confirm & Book Tickets';
                }
                return;
            }

            // Stop timer on success
            clearInterval(this.timerInterval);

            showToast('Booking successfully confirmed!', 'success');
            setTimeout(() => {
                window.location.href = `/booking/confirmation/${data.booking_id}`;
            }, 500);

        } catch (err) {
            console.error('Submission error:', err);
            showToast('Network error while processing booking. Please try again.', 'error');
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.textContent = 'Confirm & Book Tickets';
            }
        }
    }
};

const styleEl = document.createElement('style');
styleEl.textContent = `
    @keyframes spin {
        to { transform: rotate(360deg); }
    }
`;
document.head.appendChild(styleEl);

document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('booking-flow-container')) {
        BookingApp.init();
    }
});
