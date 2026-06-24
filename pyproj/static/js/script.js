// Enters "display mode": hides the sidebar, header, footer, page heading, and the
// triggering button itself, leaving only the page's own content visible (see .display-mode
// rules in style.css). Exiting requires reloading the page without a ?display=1 marker.
function enterDisplayMode() {
    document.body.classList.add('display-mode');
}

// Reloads the current page, preserving display mode across the reload if it's currently
// active (via a ?display=1 marker), unlike a plain location.reload(). Pages that need to
// resync themselves (e.g. polling that detects added/removed rows) should call this instead
// of location.reload() so a background refresh doesn't silently exit display mode.
function reloadPreservingDisplayMode() {
    const url = new URL(window.location.href);
    if (document.body.classList.contains('display-mode')) {
        url.searchParams.set('display', '1');
    } else {
        url.searchParams.delete('display');
    }
    window.location.href = url.toString();
}

document.addEventListener('DOMContentLoaded', function () {
    if (new URLSearchParams(window.location.search).get('display') === '1') {
        enterDisplayMode();
    }
});

// Copies the text in btn's data-copy-text attribute to the clipboard, then briefly
// swaps the button's icon to a checkmark as feedback before reverting it.
function copyToClipboard(btn) {
    navigator.clipboard.writeText(btn.dataset.copyText).then(function () {
        const icon = btn.querySelector('i');
        const originalClass = icon.className;
        icon.className = 'bi bi-check-lg';
        setTimeout(function () {
            icon.className = originalClass;
        }, 1500);
    });
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Enables drag-and-drop reordering of <tr> rows within the <tbody> identified by tbodyId.
// Each row must have a data-stage-id attribute; the new order is posted to the URL in the
// tbody's data-reorder-url attribute as JSON: {"order": [id, id, ...]}.
function initSortableReorder(tbodyId) {
    const tbody = document.getElementById(tbodyId);
    if (!tbody || typeof Sortable === 'undefined') return;

    Sortable.create(tbody, {
        handle: '.bi-grip-vertical',
        animation: 150,
        onEnd: function () {
            const order = Array.from(tbody.querySelectorAll('tr[data-stage-id]'))
                .map(function (row) { return row.dataset.stageId; });

            fetch(tbody.dataset.reorderUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken'),
                },
                body: JSON.stringify({ order: order }),
            });
        },
    });
}

// Wires up .status-btn buttons within the <tbody> identified by tbodyId so clicking one
// posts to its data-url and updates the row's status highlighting, table colour class,
// and completion date input (if returned) without reloading the page.
function initStatusButtons(tbodyId) {
    const tbody = document.getElementById(tbodyId);
    if (!tbody) return;

    tbody.addEventListener('click', function (event) {
        const button = event.target.closest('.status-btn');
        if (!button) return;

        const row = button.closest('tr');
        const group = button.closest('.status-buttons');

        fetch(button.dataset.url, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
            },
        })
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (!data.status) return;

                group.querySelectorAll('.status-btn').forEach(function (btn) {
                    const color = btn.dataset.color;
                    btn.classList.remove('btn-' + color, 'btn-outline-' + color);
                    btn.classList.add(btn.dataset.status === data.status ? 'btn-' + color : 'btn-outline-' + color);
                });

                row.classList.remove('table-info', 'table-warning', 'table-success');
                if (data.table_class) {
                    row.classList.add(data.table_class);
                }

                if (data.completion_date) {
                    const completionInput = row.querySelector('input[name="completion_date"]');
                    if (completionInput) {
                        completionInput.value = data.completion_date;
                    }
                }
            });
    });
}

function initServerFilter(resultsId) {
    const input = document.getElementById('list-search');
    const clearBtn = document.getElementById('list-search-clear');
    const resultsDiv = document.getElementById(resultsId);
    if (!input || !resultsDiv) return;

    let debounceTimer;

    async function fetchResults(q) {
        const url = q ? '?q=' + encodeURIComponent(q) : '?';
        try {
            const response = await fetch(url);
            const html = await response.text();
            const doc = new DOMParser().parseFromString(html, 'text/html');
            const newResults = doc.getElementById(resultsId);
            if (newResults) {
                resultsDiv.innerHTML = newResults.innerHTML;
            }
            history.pushState(null, '', url);
        } catch (e) {
            console.error('Filter fetch failed:', e);
        }
    }

    input.addEventListener('input', function() {
        const q = input.value.trim();
        clearBtn.style.display = q ? '' : 'none';
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(function() { fetchResults(q); }, 300);
    });

    clearBtn.addEventListener('click', function() {
        input.value = '';
        clearBtn.style.display = 'none';
        fetchResults('');
        input.focus();
    });
}

// Set fixed margin for body content to account for sidebar
document.addEventListener('DOMContentLoaded', function() {
    const sidebar = document.querySelector('#sidebar');
    const body = document.querySelector('.body');
    const toggler = document.querySelector('[data-coreui-toggle="sidebar"]');
    
    if (!sidebar || !body) return;
    
    function setBodyMargin() {
        if (window.innerWidth < 992) {
            // On mobile/tablet, sidebar overlays, so no margin needed
            body.style.marginLeft = '0';
        } else {
            // On desktop, sidebar is always visible and expanded
            body.style.marginLeft = '256px';
        }
    }
    
    // Initialize sidebar state based on screen size
    function initializeSidebar() {
        if (window.innerWidth < 992) {
            // On mobile, hide sidebar by default (remove show class)
            // Wait a bit to ensure CoreUI is initialized
            setTimeout(function() {
                sidebar.classList.remove('sidebar-lg-show');
            }, 100);
        } else {
            // On desktop, show sidebar
            sidebar.classList.add('sidebar-lg-show');
        }
        setBodyMargin();
    }
    
    // Handle toggle - prevent on desktop, allow on mobile
    if (toggler) {
        toggler.addEventListener('click', function(e) {
            if (window.innerWidth >= 992) {
                // Prevent toggle on desktop
                e.preventDefault();
                e.stopPropagation();
                return false;
            }
            // On mobile, let CoreUI handle it, but ensure it works
            // Don't prevent default - let CoreUI toggle the class
        });
    }
    
    // Initialize sidebar state
    initializeSidebar();
    
    // Add manual toggle handler for mobile (works regardless of CoreUI)
    if (toggler) {
        // Remove the data attribute to prevent CoreUI from handling it
        // We'll handle it manually
        const originalBreakpoint = toggler.getAttribute('data-coreui-breakpoint');
        toggler.removeAttribute('data-coreui-toggle');
        toggler.removeAttribute('data-coreui-breakpoint');
        
        toggler.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            if (window.innerWidth >= 992) {
                // Desktop - do nothing
                return false;
            }
            
            // Mobile - manually toggle
            const isShown = sidebar.classList.contains('sidebar-lg-show');
            if (isShown) {
                sidebar.classList.remove('sidebar-lg-show');
            } else {
                sidebar.classList.add('sidebar-lg-show');
            }
            
            return false
        });
    }
    
    // Update on window resize
    let resizeTimeout;
    window.addEventListener('resize', function() {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(function() {
            initializeSidebar();
        }, 100);
    });
    
    // Listen for class changes to handle backdrop on mobile
    if (sidebar) {
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
                    if (window.innerWidth < 992) {
                        // On mobile, check if sidebar is shown
                        if (sidebar.classList.contains('sidebar-lg-show')) {
                            // Sidebar is shown, add backdrop if needed
                            if (!document.querySelector('.sidebar-backdrop')) {
                                const backdrop = document.createElement('div');
                                backdrop.className = 'sidebar-backdrop';
                                backdrop.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1029;';
                                backdrop.addEventListener('click', function() {
                                    if (toggler) toggler.click();
                                });
                                document.body.appendChild(backdrop);
                            }
                        } else {
                            // Sidebar is hidden, remove backdrop
                            const backdrop = document.querySelector('.sidebar-backdrop');
                            if (backdrop) {
                                backdrop.remove();
                            }
                        }
                    }
                }
            });
        });
        
        observer.observe(sidebar, {
            attributes: true,
            attributeFilter: ['class']
        });
    }
});
