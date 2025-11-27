/**
 * Loader Handler - Page Unload Loader
 * Shows loading animation when user navigates away from page
 * Reusable across all dashboard pages
 */

(function() {
    'use strict';

    // Show loader before page unload
    window.addEventListener('beforeunload', function (e) {
        const loader = document.getElementById('loader');
        if (loader) {
            loader.style.display = 'flex';
        }
    });

})();
