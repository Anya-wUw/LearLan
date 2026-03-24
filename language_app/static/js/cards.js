// Shared utilities for card interactions (used across chat.html and group.html)

/**
 * Escape HTML special characters for safe insertion into HTML attributes.
 */
function escapeHTML(str) {
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(str || ''));
  return div.innerHTML;
}

/**
 * Show a floating toast notification for 3 seconds.
 * type: 'warning' | 'danger' | 'success' | 'info'
 */
function showToast(msg, type = 'warning') {
  const toast = document.createElement('div');
  toast.style.cssText = [
    'position:fixed', 'bottom:1.5rem', 'left:50%', 'transform:translateX(-50%)',
    'z-index:9999', 'padding:.65rem 1.25rem', 'border-radius:8px',
    'font-size:.9rem', 'font-weight:600', 'box-shadow:0 4px 16px rgba(0,0,0,.18)',
    'pointer-events:none', 'transition:opacity .4s',
  ].join(';');
  const colors = {
    warning:  ['#fff3cd','#856404'],
    danger:   ['#f8d7da','#842029'],
    success:  ['#d1e7dd','#0f5132'],
    info:     ['#cff4fc','#055160'],
    primary:  ['#e0dcf0','#5b4fcf'],
  };
  const [bg, fg] = colors[type] || colors.info;
  toast.style.background = bg;
  toast.style.color = fg;
  toast.textContent = msg;
  document.body.appendChild(toast);
  setTimeout(() => { toast.style.opacity = '0'; }, 2600);
  setTimeout(() => toast.remove(), 3100);
}
