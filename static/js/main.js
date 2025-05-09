// Main JavaScript file for AI Podcasts Dashboard

document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize Bootstrap popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Auto-dismiss alerts after 5 seconds
    setTimeout(function() {
        var alerts = document.querySelectorAll('.alert:not(.alert-warning):not(.alert-info)');
        alerts.forEach(function(alert) {
            var bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);
    
    // Add formatted date-time to any element with the `.datetime` class
    document.querySelectorAll('.datetime').forEach(function(el) {
        var date = new Date(el.getAttribute('data-datetime'));
        if (!isNaN(date)) {
            el.textContent = date.toLocaleString();
        }
    });
    
    // Add collapse functionality to any element with the `.collapsible` class
    document.querySelectorAll('.collapsible-trigger').forEach(function(trigger) {
        trigger.addEventListener('click', function() {
            var target = document.querySelector(this.getAttribute('data-target'));
            if (target) {
                if (target.style.display === 'none' || !target.style.display) {
                    target.style.display = 'block';
                    this.innerHTML = this.innerHTML.replace('down', 'up');
                } else {
                    target.style.display = 'none';
                    this.innerHTML = this.innerHTML.replace('up', 'down');
                }
            }
        });
    });
    
    // Function to format file size
    window.formatFileSize = function(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    };
    
    // Function to format date
    window.formatDate = function(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
    };
    
    // Function to truncate text with ellipsis
    window.truncateText = function(text, maxLength) {
        if (text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    };
});
