// Shared utilities for card interactions (used across chat.html and group.html)

/**
 * Escape HTML special characters for safe insertion into HTML attributes.
 */
function escapeHTML(str) {
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(str || ''));
  return div.innerHTML;
}
