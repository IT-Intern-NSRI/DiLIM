<?php
/**
 * Theme setup file for the Lab Manual site. WordPress loads this
 * automatically on every request. This file contains one small real
 * function (asset loading) - everything else about the site's
 * structure (post type, fields) is configured through the Pods admin
 * UI, not code, per the "non-technical maintenance" requirement.
 */

function lab_manual_enqueue_assets() {
    /**
     * Input: none (WordPress calls this automatically on the
     *        "wp_enqueue_scripts" hook, for every front-end page load).
     * Output: none (side effect: registers and loads tabs.css and
     *         tabs.js on every page so the tab interface renders and
     *         behaves correctly).
     *
     * Pseudocode:
     * 1. wp_enqueue_style('lab-manual-tabs',
     *    get_template_directory_uri() . '/assets/tabs.css').
     * 2. wp_enqueue_script('lab-manual-tabs',
     *    get_template_directory_uri() . '/assets/tabs.js', [], false, true)
     *    - "true" as the last arg loads it in the footer, after the tab
     *    markup already exists in the DOM.
     */
    wp_enqueue_style( 'lab-manual-tabs', get_template_directory_uri() . '/assets/tabs.css' );
    wp_enqueue_script( 'lab-manual-tabs', get_template_directory_uri() . '/assets/tabs.js', array(), false, true );
}
add_action( 'wp_enqueue_scripts', 'lab_manual_enqueue_assets' );
