/**
 * Modal Handlers - Reusable Modal Interactions
 * Handles trade modals (Add Funds, Withdraw) with success modal flow
 * Reusable across trades.html and copy_traders.html
 */

(function() {
    'use strict';

    function initModalHandlers() {
        // Check if Bootstrap Modal is available
        if (typeof bootstrap === 'undefined' || !bootstrap.Modal) {
            console.warn('Bootstrap Modal not available');
            return;
        }

        // Handle Add More Funds flow - show success modal
        const addToTradeButtons = document.querySelectorAll('button[name="top"]');

        addToTradeButtons.forEach(function(button) {
            button.addEventListener('click', function(e) {
                e.preventDefault();

                // Get the modal this button belongs to
                const modal = button.closest('.modal');

                // Hide the current modal
                const currentModal = bootstrap.Modal.getInstance(modal);
                if (currentModal) {
                    currentModal.hide();
                }

                // Wait for modal to finish hiding, then show success modal
                setTimeout(function() {
                    const successModalEl = document.getElementById('successModal');
                    if (successModalEl) {
                        const successModal = new bootstrap.Modal(successModalEl);
                        successModal.show();
                    }
                }, 300);
            });
        });

        // Handle Withdraw Funds flow - show success modal
        const withdrawButtons = document.querySelectorAll('button[name="withdraw"]');

        withdrawButtons.forEach(function(button) {
            button.addEventListener('click', function(e) {
                e.preventDefault();

                // Get the modal this button belongs to
                const modal = button.closest('.modal');

                // Hide the current modal
                const currentModal = bootstrap.Modal.getInstance(modal);
                if (currentModal) {
                    currentModal.hide();
                }

                // Wait for modal to finish hiding, then show success modal
                setTimeout(function() {
                    const successModalEl = document.getElementById('successModal');
                    if (successModalEl) {
                        const successModal = new bootstrap.Modal(successModalEl);
                        successModal.show();

                        // Change the success message for withdraw
                        const successMessage = document.querySelector('.success-message');
                        if (successMessage) {
                            successMessage.textContent = 'Funds withdrawn successfully';
                        }
                    }
                }, 300);
            });
        });

        // Handle Copy Trader flow - show success modal
        const copyButtons = document.querySelectorAll('button[name="copy"]');

        copyButtons.forEach(function(button) {
            button.addEventListener('click', function(e) {
                e.preventDefault();

                // Get the modal this button belongs to
                const modal = button.closest('.modal');

                // Hide the current modal
                const currentModal = bootstrap.Modal.getInstance(modal);
                if (currentModal) {
                    currentModal.hide();
                }

                // Wait for modal to finish hiding, then show success modal
                setTimeout(function() {
                    const successModalEl = document.getElementById('successModal');
                    if (successModalEl) {
                        const successModal = new bootstrap.Modal(successModalEl);
                        successModal.show();

                        // Change the success message for copy trader
                        const successMessage = document.querySelector('.success-message');
                        if (successMessage) {
                            successMessage.textContent = 'Trade copied';
                        }
                    }
                }, 300);
            });
        });

        // Reset success message when modal is hidden
        const successModalEl = document.getElementById('successModal');
        if (successModalEl) {
            successModalEl.addEventListener('hidden.bs.modal', function() {
                const successMessage = document.querySelector('.success-message');
                if (successMessage) {
                    // Reset to default message based on which page we're on
                    if (document.body.classList.contains('copy-traders-page')) {
                        successMessage.textContent = 'Trade copied';
                    } else {
                        successMessage.textContent = 'Amount topped';
                    }
                }

                // Clean up any stray backdrops
                document.querySelectorAll('.modal-backdrop').forEach(backdrop => backdrop.remove());
                document.body.classList.remove('modal-open');
                document.body.style.removeProperty('padding-right');
                document.body.style.removeProperty('overflow');
            });
        }
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initModalHandlers);
    } else {
        initModalHandlers();
    }

})();
