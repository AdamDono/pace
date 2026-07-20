/**
 * Universal Upload Progress System
 * Automatically shows progress bars for all file uploads
 */

(function() {
    'use strict';

    // Create global progress overlay
    function createProgressOverlay() {
        if (document.getElementById('upload-progress-overlay')) return;
        
        const overlay = document.createElement('div');
        overlay.id = 'upload-progress-overlay';
        overlay.className = 'fixed inset-0 bg-black bg-opacity-50 hidden flex items-center justify-center z-50';
        overlay.innerHTML = `
            <div class="bg-white rounded-lg shadow-2xl p-8 max-w-md w-full mx-4">
                <div class="mb-4">
                    <h3 class="text-xl font-bold text-gray-900 mb-2" id="upload-title">Uploading File...</h3>
                    <p class="text-sm text-gray-600" id="upload-subtitle">Please wait while your file is being uploaded</p>
                </div>
                
                <!-- Progress Bar -->
                <div class="mb-4">
                    <div class="flex justify-between items-center mb-2">
                        <span class="text-sm font-medium text-gray-700" id="upload-filename">Preparing...</span>
                        <span class="text-sm font-bold text-blue-600" id="upload-percentage">0%</span>
                    </div>
                    <div class="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
                        <div id="upload-progress-bar" 
                             class="h-full bg-gradient-to-r from-blue-500 to-purple-600 rounded-full transition-all duration-300 ease-out"
                             style="width: 0%"></div>
                    </div>
                </div>
                
                <!-- File Info -->
                <div class="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4">
                    <div class="flex items-center justify-between text-xs text-gray-600">
                        <span>📦 Size: <strong id="upload-size">-</strong></span>
                        <span>⚡ Speed: <strong id="upload-speed">-</strong></span>
                        <span>⏱️ Time: <strong id="upload-time">-</strong></span>
                    </div>
                </div>
                
                <!-- Status Messages -->
                <div id="upload-status" class="text-sm text-center text-gray-500"></div>
                
                <!-- Cancel Button (optional) -->
                <button id="upload-cancel-btn" 
                        class="hidden mt-4 w-full px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors">
                    Cancel Upload
                </button>
            </div>
        `;
        document.body.appendChild(overlay);
    }

    // Show progress overlay
    function showProgress(message = 'Uploading File...') {
        const overlay = document.getElementById('upload-progress-overlay');
        const title = document.getElementById('upload-title');
        if (overlay && title) {
            title.textContent = message;
            overlay.classList.remove('hidden');
        }
    }

    // Hide progress overlay
    function hideProgress() {
        const overlay = document.getElementById('upload-progress-overlay');
        if (overlay) {
            overlay.classList.add('hidden');
            resetProgress();
        }
    }

    // Update progress
    function updateProgress(percentage, loaded, total, speed) {
        const bar = document.getElementById('upload-progress-bar');
        const percentText = document.getElementById('upload-percentage');
        const sizeText = document.getElementById('upload-size');
        const speedText = document.getElementById('upload-speed');
        const timeText = document.getElementById('upload-time');
        
        if (bar) bar.style.width = percentage + '%';
        if (percentText) percentText.textContent = Math.round(percentage) + '%';
        
        if (sizeText && loaded && total) {
            sizeText.textContent = formatBytes(loaded) + ' / ' + formatBytes(total);
        }
        
        if (speedText && speed) {
            speedText.textContent = formatBytes(speed) + '/s';
        }
        
        if (timeText && speed && total && loaded) {
            const remaining = (total - loaded) / speed;
            timeText.textContent = formatTime(remaining);
        }
    }

    // Reset progress
    function resetProgress() {
        updateProgress(0, 0, 0, 0);
        const filename = document.getElementById('upload-filename');
        const status = document.getElementById('upload-status');
        if (filename) filename.textContent = 'Preparing...';
        if (status) status.textContent = '';
    }

    // Format bytes
    function formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    }

    // Format time
    function formatTime(seconds) {
        if (seconds < 60) return Math.round(seconds) + 's';
        if (seconds < 3600) return Math.round(seconds / 60) + 'm ' + Math.round(seconds % 60) + 's';
        return Math.round(seconds / 3600) + 'h';
    }

    // Intercept form submissions with file inputs
    function interceptFormSubmits() {
        document.addEventListener('submit', function(e) {
            const form = e.target;
            const fileInputs = form.querySelectorAll('input[type="file"]');
            
            // Check if form has file inputs with files
            let hasFiles = false;
            fileInputs.forEach(input => {
                if (input.files && input.files.length > 0) {
                    hasFiles = true;
                }
            });
            
            if (!hasFiles) return; // No files, proceed normally
            
            // Check if form already has custom loading message
            const loadingMessage = form.getAttribute('data-loading');
            if (loadingMessage) return; // Use existing loading spinner
            
            e.preventDefault();
            
            // Get file info
            let fileName = 'File';
            let fileSize = 0;
            fileInputs.forEach(input => {
                if (input.files && input.files[0]) {
                    fileName = input.files[0].name;
                    fileSize = input.files[0].size;
                }
            });
            
            // Show progress
            showProgress('Uploading ' + fileName);
            document.getElementById('upload-filename').textContent = fileName;
            
            // Create FormData
            const formData = new FormData(form);
            
            // Upload with XMLHttpRequest for progress tracking
            const xhr = new XMLHttpRequest();
            const startTime = Date.now();
            let lastLoaded = 0;
            let lastTime = startTime;
            
            xhr.upload.addEventListener('progress', function(e) {
                if (e.lengthComputable) {
                    const percentage = (e.loaded / e.total) * 100;
                    const currentTime = Date.now();
                    const timeDiff = (currentTime - lastTime) / 1000; // seconds
                    const loadedDiff = e.loaded - lastLoaded;
                    const speed = loadedDiff / timeDiff;
                    
                    updateProgress(percentage, e.loaded, e.total, speed);
                    
                    lastLoaded = e.loaded;
                    lastTime = currentTime;
                }
            });
            
            xhr.addEventListener('load', function() {
                if (xhr.status >= 200 && xhr.status < 400) {
                    updateProgress(100, fileSize, fileSize, 0);
                    document.getElementById('upload-status').textContent = '✓ Upload complete! Redirecting...';
                    
                    setTimeout(() => {
                        if (xhr.responseURL && xhr.responseURL !== window.location.href) {
                            window.location.href = xhr.responseURL;
                        } else {
                            // Reload or parse response
                            try {
                                const response = JSON.parse(xhr.responseText);
                                if (response.redirect) {
                                    window.location.href = response.redirect;
                                    return;
                                }
                            } catch(e) {}
                            window.location.reload();
                        }
                    }, 400);
                } else {
                    hideProgress();
                    alert('Upload failed (HTTP ' + xhr.status + '). Please check file format or try again.');
                }
            });
            
            xhr.addEventListener('error', function() {
                hideProgress();
                alert('Upload error. Please check your connection and try again.');
            });
            
            xhr.addEventListener('abort', function() {
                hideProgress();
                alert('Upload cancelled.');
            });
            
            xhr.open(form.method || 'POST', form.action || window.location.href);
            xhr.send(formData);
        });
    }

    // Initialize on page load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            createProgressOverlay();
            interceptFormSubmits();
        });
    } else {
        createProgressOverlay();
        interceptFormSubmits();
    }

    // Expose global functions
    window.UploadProgress = {
        show: showProgress,
        hide: hideProgress,
        update: updateProgress
    };

    console.log('✅ Upload Progress System initialized');
})();
