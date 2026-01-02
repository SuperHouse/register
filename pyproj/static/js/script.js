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
