// static/js/script.js (REPLACEMENT)
let socket;
let currentControlType = null;
let currentPage = 0;        // 0-based
let totalPages = 0;
let zoomLevel = 100;        // percent
let serverPollInterval = null;

document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
    connectWebSocket();
});

function connectWebSocket() {
    if (typeof io === 'undefined') return;
    socket = io();
    
    socket.on('connect', function() {
        showToast('Connected to server', 'success');
        updateStatusIndicator('connected', 'Connected');
    });
    
    socket.on('disconnect', function() {
        showToast('Disconnected from server', 'error');
        updateStatusIndicator('disconnected', 'Disconnected');
    });
    
    // If your backend emits page updates via socket.io, handle them here:
    socket.on('page_update', function(data) {
        // Expecting data: { page_number: 1-based, total_pages: n, image_data?: 'data:image/...' }
        if (data.page_number !== undefined) {
            const serverPageZeroBased = data.page_number - 1;
            if (serverPageZeroBased !== currentPage) {
                currentPage = serverPageZeroBased;
                if (data.total_pages !== undefined) totalPages = data.total_pages;
                updatePageInfo();
                loadPage(currentPage);
            }
        }
        if (data.image_data) {
            updatePageDisplay(data);
        }
    });
    
    socket.on('control_status', function(data) {
        updateControlStatus(data);
    });
    
    socket.on('connection_status', function(data) {
        console.log('Connection status:', data.status);
    });
}

function initializeApp() {
    setupFileUpload();
    setupControlSelection();
    setupControlButtons();
    setupNavigationButtons();
    setupViewerControls();
    startServerPolling();
}

function setupFileUpload() {
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('pdfFile');
    
    if (!uploadArea || !fileInput) return;
    
    uploadArea.addEventListener('click', () => fileInput.click());
    
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.style.borderColor = 'var(--primary)';
        uploadArea.style.background = 'rgba(99, 102, 241, 0.05)';
    });
    
    uploadArea.addEventListener('dragleave', () => {
        uploadArea.style.borderColor = 'var(--border)';
        uploadArea.style.background = '';
    });
    
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.style.borderColor = 'var(--border)';
        uploadArea.style.background = '';
        
        const files = e.dataTransfer.files;
        if (files.length > 0 && files[0].type === 'application/pdf') {
            handleFileUpload(files[0]);
        }
    });
    
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileUpload(e.target.files[0]);
        }
    });
}

function handleFileUpload(file) {
    if (file.size > 16 * 1024 * 1024) {
        showStatus('File size must be less than 16MB', 'error');
        return;
    }
    
    const formData = new FormData();
    formData.append('pdf_file', file);
    
    showUploadProgress(true);
    showStatus('Uploading PDF...', 'info');
    
    fetch('/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        showUploadProgress(false);
        
        if (data.success) {
            showStatus('PDF uploaded successfully!', 'success');
            showToast('Document uploaded successfully!', 'success');
            
            document.getElementById('startBtn').disabled = false;
            document.getElementById('documentName').textContent = file.name;
            
            totalPages = data.total_pages || 0;
            currentPage = 0;
            
            loadPageCount();
            showViewer();
        } else {
            showStatus('Upload failed: ' + data.error, 'error');
            showToast('Upload failed!', 'error');
        }
    })
    .catch(error => {
        showUploadProgress(false);
        console.error('Upload error:', error);
        showStatus('Upload failed. Please try again.', 'error');
        showToast('Upload failed!', 'error');
    });
}

function showUploadProgress(show) {
    const placeholder = document.querySelector('.upload-placeholder');
    const progress = document.getElementById('uploadProgress');
    
    if (!placeholder || !progress) return;
    
    if (show) {
        placeholder.style.display = 'none';
        progress.style.display = 'flex';
        
        // Simulate progress animation
        const progressFill = document.querySelector('.progress-fill');
        if (!progressFill) return;
        let width = 0;
        const interval = setInterval(() => {
            if (width >= 90) {
                clearInterval(interval);
            } else {
                width += 10;
                progressFill.style.width = width + '%';
            }
        }, 200);
    } else {
        placeholder.style.display = 'block';
        progress.style.display = 'none';
    }
}

function setupControlSelection() {
    const controlOptions = document.querySelectorAll('.control-option');
    if (!controlOptions) return;
    
    controlOptions.forEach(option => {
        option.addEventListener('click', function() {
            // Remove active class from all options
            controlOptions.forEach(opt => opt.classList.remove('active'));
            
            // Add active class to selected option
            this.classList.add('active');
            
            // Set current control type
            currentControlType = this.dataset.control;
            
            updateControlStatus({
                active: false,
                type: null,
                message: `Selected: ${this.querySelector('h3').textContent} - Click Start to begin`
            });
            
            showToast(`Selected: ${this.querySelector('h3').textContent}`, 'info');
        });
    });
}

function setupControlButtons() {
    const startBtn = document.getElementById('startBtn');
    const stopBtn = document.getElementById('stopBtn');
    if (!startBtn || !stopBtn) return;
    
    startBtn.addEventListener('click', startControl);
    stopBtn.addEventListener('click', stopControl);
}

function startControl() {
    if (!currentControlType) {
        showToast('Please select a control method first!', 'error');
        return;
    }
    
    if (!totalPages || totalPages === 0) {
        showToast('Please upload a PDF first!', 'error');
        return;
    }
    
    showToast(`Starting ${currentControlType.replace('_', ' ')} control...`, 'info');
    
    fetch('/start_control', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            control_type: currentControlType
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(data.message, 'success');
            document.getElementById('startBtn').disabled = true;
            document.getElementById('stopBtn').disabled = false;
            
            updateStatusIndicator('active', `${currentControlType.replace('_', ' ')} Active`);
        } else {
            showToast('Failed to start: ' + data.error, 'error');
        }
    })
    .catch(error => {
        console.error('Start control error:', error);
        showToast('Failed to start control.', 'error');
    });
}

function stopControl() {
    showToast('Stopping control...', 'info');
    
    fetch('/stop_control', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(data.message, 'success');
            document.getElementById('startBtn').disabled = false;
            document.getElementById('stopBtn').disabled = true;
            
            updateStatusIndicator('connected', 'Ready');
        }
    })
    .catch(error => {
        console.error('Stop control error:', error);
        showToast('Failed to stop control.', 'error');
    });
}

function setupNavigationButtons() {
    const prev = document.getElementById('prevBtn');
    const next = document.getElementById('nextBtn');
    const first = document.getElementById('firstBtn');
    const last = document.getElementById('lastBtn');
    const pageInput = document.getElementById('pageInput');
    
    if (prev) prev.addEventListener('click', () => changePage(-1));
    if (next) next.addEventListener('click', () => changePage(1));
    if (first) first.addEventListener('click', () => gotoPage(0));
    if (last) last.addEventListener('click', () => gotoPage(totalPages - 1));
    
    if (pageInput) pageInput.addEventListener('change', (e) => {
        const pageNum = parseInt(e.target.value) - 1;
        if (pageNum >= 0 && pageNum < totalPages) {
            gotoPage(pageNum);
        } else {
            e.target.value = currentPage + 1;
        }
    });
}

function setupViewerControls() {
    const zoomIn = document.getElementById('zoomInBtn');
    const zoomOut = document.getElementById('zoomOutBtn');
    const fitBtn = document.getElementById('fitToScreenBtn');
    const fullBtn = document.getElementById('fullscreenBtn');

    if (zoomIn) zoomIn.addEventListener('click', () => changeZoom(25));
    if (zoomOut) zoomOut.addEventListener('click', () => changeZoom(-25));
    if (fitBtn) fitBtn.addEventListener('click', fitToScreen);
    if (fullBtn) fullBtn.addEventListener('click', toggleFullscreen);
}

function changePage(delta) {
    const newPage = currentPage + delta;
    if (newPage >= 0 && newPage < totalPages) {
        gotoPage(newPage);
    }
}

function gotoPage(pageNum) {
    fetch('/goto_page', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            page_num: pageNum
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            currentPage = pageNum;
            updatePageInfo();
            loadPage(currentPage);
        }
    })
    .catch(error => {
        console.error('Page change error:', error);
    });
}

function changeZoom(delta) {
    zoomLevel = Math.max(25, Math.min(500, zoomLevel + delta));
    updateZoomDisplay();
    loadPage(currentPage);
}

function fitToScreen() {
    zoomLevel = 100;
    updateZoomDisplay();
    loadPage(currentPage);
}

function toggleFullscreen() {
    const viewer = document.getElementById('pdfViewer');
    if (!viewer) return;
    
    if (!document.fullscreenElement) {
        viewer.requestFullscreen().catch(err => {
            console.error('Error attempting to enable fullscreen:', err);
        });
    } else {
        document.exitFullscreen();
    }
}

function loadPageCount() {
    fetch('/get_page_count')
    .then(response => response.json())
    .then(data => {
        if (data.page_count !== undefined) {
            totalPages = data.page_count;
            currentPage = 0;
            updatePageInfo();
            loadPage(currentPage);
        }
    })
    .catch(error => {
        console.error('Error loading page count:', error);
    });
}

/*
 * loadPage: preload the image first, then swap into DOM to avoid flicker
 * pageNum is 0-based
 */
function loadPage(pageNum) {
    const img = document.getElementById('pdfImage');
    const spinner = document.getElementById('loadingSpinner');
    if (!img || !spinner) return;

    spinner.style.display = 'flex';

    const timestamp = new Date().getTime();
    const zoomParam = zoomLevel / 100;
    const newSrc = `/get_page_image/${pageNum}?t=${timestamp}&zoom=${zoomParam}`;

    // Preload
    const pre = new Image();
    pre.onload = function() {
        // swap only after loaded to prevent flicker
        img.src = newSrc;
        spinner.style.display = 'none';
        img.style.display = 'block';
        img.classList.add('fade-in');
        setTimeout(() => img.classList.remove('fade-in'), 500);
    };
    pre.onerror = function() {
        spinner.style.display = 'none';
        showToast('Error loading page image', 'error');
    };
    pre.src = newSrc;
}

/*
 * updatePageDisplay: handle socket pushes with image_data (if backend sends image as data URL)
 */
function updatePageDisplay(data) {
    if (data.image_data) {
        const img = document.getElementById('pdfImage');
        const spinner = document.getElementById('loadingSpinner');
        if (!img || !spinner) return;

        spinner.style.display = 'none';
        img.src = data.image_data;
        img.style.display = 'block';
        img.classList.add('fade-in');
        setTimeout(() => img.classList.remove('fade-in'), 500);
    }

    if (data.page_number !== undefined) {
        currentPage = data.page_number - 1;
        updatePageInfo();
    }
}

function updatePageInfo() {
    const pageInfo = document.getElementById('pageInfo');
    const pageInput = document.getElementById('pageInput');
    const totalPagesEl = document.getElementById('totalPages');

    if (pageInfo) pageInfo.textContent = `Page ${currentPage + 1} of ${totalPages}`;
    if (pageInput) pageInput.value = currentPage + 1;
    if (totalPagesEl) totalPagesEl.textContent = totalPages;
}

function updateZoomDisplay() {
    const z = document.getElementById('zoomLevel');
    if (z) z.textContent = `${zoomLevel}%`;
}

function updateControlStatus(data) {
    const statusElement = document.getElementById('controlStatus');
    if (!statusElement) return;
    
    if (data.active) {
        statusElement.innerHTML = `
            <div class="status-info" style="background: rgba(16, 185, 129, 0.1); color: var(--secondary);">
                <i class="fas fa-check-circle"></i>
                <span>${data.message}</span>
            </div>
        `;
    } else if (data.type) {
        statusElement.innerHTML = `
            <div class="status-info">
                <i class="fas fa-info-circle"></i>
                <span>${data.message}</span>
            </div>
        `;
    } else {
        statusElement.innerHTML = `
            <div class="status-info">
                <i class="fas fa-info-circle"></i>
                <span>Select a control method and click Start</span>
            </div>
        `;
    }
}

function updateStatusIndicator(status, text) {
    const indicator = document.getElementById('statusIndicator');
    if (!indicator) return;
    const dot = indicator.querySelector('.status-dot');
    const textSpan = document.getElementById('statusText');
    
    if (dot) {
        dot.className = 'status-dot';
        dot.classList.add(status);
    }
    if (textSpan) textSpan.textContent = text;
}

function showViewer() {
    const v = document.getElementById('viewerSection');
    if (!v) return;
    v.style.display = 'block';
    v.classList.add('fade-in');
}

function showStatus(message, type) {
    const statusElement = document.getElementById('uploadStatus');
    if (!statusElement) return;
    statusElement.textContent = message;
    statusElement.className = `status-message status-${type}`;
}

function showToast(message, type) {
    const toast = document.getElementById('statusToast');
    if (!toast) return;
    const toastIcon = toast.querySelector('.toast-icon');
    const toastMessage = toast.querySelector('.toast-message');
    
    // Reset
    toastIcon.className = 'toast-icon';
    toast.classList.remove('toast-success', 'toast-error', 'toast-info');
    
    if (type === 'success') {
        toastIcon.classList.add('fas', 'fa-check-circle');
        toast.classList.add('toast-success');
    } else if (type === 'error') {
        toastIcon.classList.add('fas', 'fa-exclamation-circle');
        toast.classList.add('toast-error');
    } else {
        toastIcon.classList.add('fas', 'fa-info-circle');
        toast.classList.add('toast-info');
    }
    
    if (toastMessage) toastMessage.textContent = message;
    toast.classList.add('show');
    
    setTimeout(() => {
        toast.classList.remove('show', 'toast-success', 'toast-error', 'toast-info');
    }, 4000);
}

/*
 * Poll server for current page (so controller-driven changes are reflected on UI)
 */
function pollServerCurrentPage() {
    fetch('/get_current_page')
    .then(res => res.json())
    .then(data => {
        if (data && data.current_page !== undefined) {
            const serverPage = data.current_page;
            if (data.total_pages !== undefined && data.total_pages !== totalPages) {
                totalPages = data.total_pages;
            }
            if (serverPage !== currentPage) {
                currentPage = serverPage;
                updatePageInfo();
                loadPage(currentPage);
            }
        }
    })
    .catch(err => {
        // silent fail — keep polling
        //console.debug('poll error', err);
    });
}

function startServerPolling() {
    // If already polling, clear first
    if (serverPollInterval) {
        clearInterval(serverPollInterval);
    }
    // Poll every 800ms for server-side page changes (tuned for low-latency without hammering)
    serverPollInterval = setInterval(() => {
        // Poll only if viewer visible and there's a document
        const viewer = document.getElementById('viewerSection');
        if (viewer && viewer.style.display !== 'none' && totalPages > 0) {
            pollServerCurrentPage();
        }
    }, 800);
}

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (serverPollInterval) {
        clearInterval(serverPollInterval);
    }
    if (socket) {
        socket.disconnect();
    }
});

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    if (e.target.tagName === 'INPUT') return;
    
    switch(e.key) {
        case 'ArrowLeft':
            e.preventDefault();
            changePage(-1);
            break;
        case 'ArrowRight':
            e.preventDefault();
            changePage(1);
            break;
        case 'Home':
            e.preventDefault();
            gotoPage(0);
            break;
        case 'End':
            e.preventDefault();
            gotoPage(totalPages - 1);
            break;
        case '+':
            e.preventDefault();
            changeZoom(25);
            break;
        case '-':
            e.preventDefault();
            changeZoom(-25);
            break;
        case '0':
            e.preventDefault();
            fitToScreen();
            break;
    }
});
