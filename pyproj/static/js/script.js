// Set fixed margin for body content to account for always-visible sidebar
document.addEventListener('DOMContentLoaded', function() {
    const sidebar = document.querySelector('#sidebar');
    const body = document.querySelector('.body');
    
    if (!sidebar || !body) return;
    
    function setBodyMargin() {
        if (window.innerWidth < 768) {
            body.style.marginLeft = '0';
        } else {
            // Sidebar is always visible and expanded, so use full width
            body.style.marginLeft = '256px';
        }
    }
    
    // Set initial margin
    setBodyMargin();
    
    // Update on window resize
    window.addEventListener('resize', setBodyMargin);
});
