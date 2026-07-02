/**
 * Client-side behavior for the tab interface on
 * single-manual_document.php. Unlike the other frontend files, this one
 * DOES contain real logic (interaction handling), so - like the backend
 * Python/PHP files - it is broken into named functions with pseudocode
 * rather than just described in prose.
 */

function initTabs() {
    /**
     * Input: none (runs once, after the page's DOM has fully loaded).
     * Output: none (side effect: attaches a click handler to every tab
     *         button on the page, and activates the first tab by
     *         default so a section is always visible on page load).
     *
     * Pseudocode:
     * 1. Select all elements with class "tab-button" (each is expected
     *    to have a data-section-id attribute matching a ".tab-panel"
     *    element's id, both rendered by single-manual_document.php).
     * 2. For each button, add a "click" event listener that calls
     *    switchTab(button.dataset.sectionId).
     * 3. If at least one tab button exists, call switchTab() using the
     *    first button's section id, so a panel is visible by default
     *    instead of a blank page.
     */
    var buttons = document.querySelectorAll('.tab-button');

    buttons.forEach(function (button) {
        button.addEventListener('click', function () {
            switchTab(button.dataset.sectionId);
        });
    });

    if (buttons.length > 0) {
        switchTab(buttons[0].dataset.sectionId);
    }
}

function switchTab(sectionId) {
    /**
     * Input: sectionId (string) - the id of the section content panel
     *        that should become visible.
     * Output: none (side effect: shows the target panel, hides all
     *         other panels, and updates which tab button carries the
     *         "active" CSS class).
     *
     * Pseudocode:
     * 1. Select all elements with class "tab-panel"; hide each one
     *    (e.g. element.style.display = "none").
     * 2. Select the element whose id equals sectionId; make it visible
     *    (e.g. element.style.display = "block").
     * 3. Select all elements with class "tab-button"; remove the
     *    "active" class from each.
     * 4. Select the button whose data-section-id equals sectionId; add
     *    the "active" class to it.
     */
    var panels = document.querySelectorAll('.tab-panel');
    panels.forEach(function (panel) {
        panel.style.display = 'none';
    });

    var activePanel = document.getElementById(sectionId);
    if (activePanel) {
        activePanel.style.display = 'block';
    }

    var tabButtons = document.querySelectorAll('.tab-button');
    tabButtons.forEach(function (button) {
        button.classList.remove('active');
    });

    var activeButton = document.querySelector('.tab-button[data-section-id="' + sectionId + '"]');
    if (activeButton) {
        activeButton.classList.add('active');
    }
}

document.addEventListener('DOMContentLoaded', initTabs);
