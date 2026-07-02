<?php
/**
 * Must-Use plugin: forces every front-end page on the site to require a
 * logged-in WordPress account, since the manual must only be viewable
 * by lab staff (not the public). Placed in wp-content/mu-plugins/ so it
 * cannot be accidentally deactivated from the normal Plugins screen.
 */

function lab_manual_force_login() {
    /**
     * Input: none (WordPress calls this automatically on the
     *        "template_redirect" hook, for every front-end request).
     * Output: none (side effect: redirects anonymous visitors to the
     *         WordPress login page, then back to the page they
     *         originally requested after they log in successfully).
     *
     * Pseudocode:
     * 1. If is_user_logged_in() is true, return immediately (let the
     *    request proceed normally).
     * 2. If the current request is already the login page itself (check
     *    against wp_login_url() / the "wp-login.php" path), return
     *    immediately, to avoid a redirect loop.
     * 3. Otherwise, build the current page's full URL (protocol + host +
     *    request URI), call wp_redirect(wp_login_url($current_url)),
     *    then exit.
     */
    if ( is_user_logged_in() ) {
        return;
    }

    if ( strpos( $_SERVER['REQUEST_URI'], 'wp-login.php' ) !== false ) {
        return;
    }

    $protocol     = is_ssl() ? 'https://' : 'http://';
    $current_url  = $protocol . $_SERVER['HTTP_HOST'] . $_SERVER['REQUEST_URI'];

    wp_redirect( wp_login_url( $current_url ) );
    exit;
}
add_action( 'template_redirect', 'lab_manual_force_login' );
