<?php
/**
 * Template for the listing/index page of all "Manual Document" posts -
 * the page a lab member lands on to browse the whole digitized manual.
 *
 * Read-only browsing only (no editing controls here) - the whole site
 * already sits behind the login wall enforced by
 * mu-plugins/force-login.php, so there's no separate "is this public"
 * check needed.
 *
 * Grouping note: this only groups documents by WordPress's built-in
 * "category" taxonomy, and only if you've actually attached that
 * taxonomy to the manual_document pod yourself (Pods Admin >
 * manual_document > Advanced Options > Built-in Taxonomies > Categories).
 * Nothing in this project's README/Pods setup instructions creates that
 * taxonomy for you, so if you haven't done that, every document just
 * falls into a single flat, alphabetically-sorted list below - that's
 * expected, not a bug.
 */

get_header();

$has_category_grouping = taxonomy_exists( 'category' ) && is_object_in_taxonomy( 'manual_document', 'category' );

/**
 * Renders one document's row: title (linked), document number, and
 * last-updated date. Shared by both the grouped and flat rendering
 * paths below so the markup only lives in one place.
 *
 * Input: none (operates on the current post in the Loop via the_ID()/
 *        the_title()/the_permalink() - must be called from inside a
 *        have_posts()/the_post() loop).
 * Output: none (echoes one <li> of markup).
 */
function lab_manual_render_document_row() {
	$document_pod = function_exists( 'pods' ) ? pods( 'manual_document', get_the_ID() ) : null;
	$doc_number   = $document_pod ? $document_pod->field( 'doc_number' ) : '';
	?>
	<li class="manual-archive__item">
		<a class="manual-archive__link" href="<?php the_permalink(); ?>">
			<span class="manual-archive__title"><?php the_title(); ?></span>
		</a>
		<span class="manual-archive__meta">
			<?php if ( ! empty( $doc_number ) ) : ?>
				<span class="manual-archive__doc-number">
					<?php echo esc_html( sprintf( __( 'Document #%s', 'lab-manual' ), $doc_number ) ); ?>
				</span>
				<span class="manual-archive__meta-sep">&middot;</span>
			<?php endif; ?>
			<span class="manual-archive__revised">
				<?php
				echo esc_html(
					sprintf(
						/* translators: %s: last modified date */
						__( 'Updated %s', 'lab-manual' ),
						get_the_modified_date()
					)
				);
				?>
			</span>
		</span>
	</li>
	<?php
}
?>

<main class="manual-archive">
	<header class="manual-archive__header">
		<h1><?php post_type_archive_title(); ?></h1>
	</header>

	<?php if ( ! have_posts() ) : ?>

		<p class="manual-archive__empty">
			<?php esc_html_e( 'No manual documents have been published yet.', 'lab-manual' ); ?>
		</p>

	<?php elseif ( $has_category_grouping ) : ?>

		<?php
		// Collect every post in the current query, bucketed by category,
		// then render one <section> per category. Posts with no category
		// fall into an "Uncategorized" bucket at the end.
		$buckets           = array();
		$uncategorized_key = '__uncategorized__';

		while ( have_posts() ) :
			the_post();

			$terms = get_the_terms( get_the_ID(), 'category' );

			if ( empty( $terms ) || is_wp_error( $terms ) ) {
				$buckets[ $uncategorized_key ]['label'] = __( 'Uncategorized', 'lab-manual' );
				$buckets[ $uncategorized_key ]['posts'][] = get_the_ID();
				continue;
			}

			foreach ( $terms as $term ) {
				$buckets[ $term->slug ]['label']   = $term->name;
				$buckets[ $term->slug ]['posts'][] = get_the_ID();
			}
		endwhile;

		foreach ( $buckets as $bucket ) :
			?>
			<section class="manual-archive__group">
				<h2 class="manual-archive__group-title"><?php echo esc_html( $bucket['label'] ); ?></h2>
				<ul class="manual-archive__list">
					<?php
					foreach ( $bucket['posts'] as $post_id ) {
						global $post;
						$post = get_post( $post_id ); // phpcs:ignore WordPress.WP.GlobalVariablesOverride
						setup_postdata( $post );
						lab_manual_render_document_row();
					}
					wp_reset_postdata();
					?>
				</ul>
			</section>
			<?php
		endforeach;
		?>

	<?php else : ?>

		<ul class="manual-archive__list">
			<?php
			while ( have_posts() ) :
				the_post();
				lab_manual_render_document_row();
			endwhile;
			?>
		</ul>

		<?php the_posts_pagination(); ?>

	<?php endif; ?>
</main>

<?php
get_footer();
