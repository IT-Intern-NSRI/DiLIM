<?php
/**
 * Template for viewing one "Manual Document" post - one digitized PDF,
 * rendered as a full webpage with a tabbed section interface and a
 * signature block.
 *
 * Data note: "sections" and "signatories" are Pods Relationship fields
 * on manual_document (NOT repeater fields - see
 * pods-repeater-issue-and-fix.md), pointing at their own "section" and
 * "signatory" Custom Post Type pods. So rendering this page means:
 *   1. get the related section/signatory post IDs via the Pods API,
 *   2. pull each related post's own fields via its own pods() object,
 *   3. sort by that item's *_order field (a Relationship field does not
 *      guarantee order on its own),
 *   4. render.
 *
 * There is deliberately no revision/effective-date field here -
 * schema.py / the extraction pipeline don't capture one. This template
 * uses WordPress's built-in "last modified" date as a stand-in; add a
 * real `revision_date` Pods field (and extraction support for it) if
 * the lab actually wants one.
 */

get_header();

if ( ! function_exists( 'pods' ) ) {
	echo '<main class="manual-document"><p>' .
		esc_html__( 'The Pods plugin is required to display this page.', 'lab-manual' ) .
		'</p></main>';
	get_footer();
	return;
}

/**
 * Pulls the fields for every post related to $parent_pod's $field_name
 * Relationship field, sorted by each related item's own $order_field.
 *
 * Input: $parent_pod (Pods) - the pods() object for the current post.
 *        $field_name (string) - the Relationship field's name, e.g.
 *        "sections" or "signatories".
 *        $related_pod_name (string) - the related Pod's name, e.g.
 *        "section" or "signatory".
 *        $order_field (string) - the field on each related item to sort
 *        by, e.g. "section_order" or "signatory_order".
 * Output: array of associative arrays, one per related item, each
 *         containing "ID" plus every field from $related_pod_name's own
 *         pods() object, sorted ascending by $order_field.
 */
function lab_manual_get_related_items( $parent_pod, $field_name, $related_pod_name, $order_field ) {
	$related = $parent_pod->field( $field_name );

	if ( empty( $related ) || ! is_array( $related ) ) {
		return array();
	}

	// A Relationship field can come back as a single associative array
	// (one related item) or a list of them (multiple) - normalize to a
	// list either way.
	if ( isset( $related['ID'] ) ) {
		$related = array( $related );
	}

	$items = array();

	foreach ( $related as $related_item ) {
		if ( empty( $related_item['ID'] ) ) {
			continue;
		}

		$item_id  = (int) $related_item['ID'];
		$item_pod = pods( $related_pod_name, $item_id );

		if ( ! $item_pod || ! $item_pod->exists() ) {
			continue;
		}

		$fields                 = $item_pod->export();
		$fields['ID']           = $item_id;
		$fields['order_value']  = isset( $fields[ $order_field ] ) ? (int) $fields[ $order_field ] : 0;

		$items[] = $fields;
	}

	usort(
		$items,
		function ( $a, $b ) {
			return $a['order_value'] <=> $b['order_value'];
		}
	);

	return $items;
}

/**
 * Resolves a Pods File-type field's value down to a plain attachment ID.
 *
 * Input: $field_value (mixed) - whatever pods()->field() returned for a
 *        File-type field (an associative array with an "ID" key in the
 *        common case, occasionally a plain numeric ID).
 * Output: int - the attachment post ID, or 0 if none/unresolvable.
 */
function lab_manual_resolve_attachment_id( $field_value ) {
	if ( is_array( $field_value ) && ! empty( $field_value['ID'] ) ) {
		return (int) $field_value['ID'];
	}

	if ( is_numeric( $field_value ) ) {
		return (int) $field_value;
	}

	return 0;
}

while ( have_posts() ) :
	the_post();

	$document_pod = pods( 'manual_document', get_the_ID() );
	$doc_number   = $document_pod ? $document_pod->field( 'doc_number' ) : '';

	$sections    = $document_pod ? lab_manual_get_related_items( $document_pod, 'sections', 'section', 'section_order' ) : array();
	$signatories = $document_pod ? lab_manual_get_related_items( $document_pod, 'signatories', 'signatory', 'signatory_order' ) : array();
	?>

	<main class="manual-document">
		<header class="manual-document__header">
			<h1 class="manual-document__title"><?php the_title(); ?></h1>
			<p class="manual-document__meta">
				<?php if ( ! empty( $doc_number ) ) : ?>
					<span class="manual-document__doc-number">
						<?php echo esc_html( sprintf( __( 'Document #%s', 'lab-manual' ), $doc_number ) ); ?>
					</span>
					<span class="manual-document__meta-sep">&middot;</span>
				<?php endif; ?>
				<span class="manual-document__revised">
					<?php
					echo esc_html(
						sprintf(
							/* translators: %s: last modified date */
							__( 'Last updated %s', 'lab-manual' ),
							get_the_modified_date()
						)
					);
					?>
				</span>
			</p>
		</header>

		<?php if ( ! empty( $sections ) ) : ?>
			<nav class="manual-document__tabs tab-row" role="tablist" aria-label="<?php esc_attr_e( 'Document sections', 'lab-manual' ); ?>">
				<?php foreach ( $sections as $index => $section ) : ?>
					<?php $panel_id = 'section-panel-' . (int) $section['ID']; ?>
					<button
						type="button"
						class="tab-button"
						data-section-id="<?php echo esc_attr( $panel_id ); ?>"
						role="tab"
						aria-selected="<?php echo 0 === $index ? 'true' : 'false'; ?>"
					>
						<?php echo esc_html( $section['section_title'] ?? '' ); ?>
					</button>
				<?php endforeach; ?>
			</nav>

			<div class="manual-document__panels">
				<?php foreach ( $sections as $section ) : ?>
					<?php $panel_id = 'section-panel-' . (int) $section['ID']; ?>
					<section id="<?php echo esc_attr( $panel_id ); ?>" class="tab-panel">
						<h2 class="tab-panel__title"><?php echo esc_html( $section['section_title'] ?? '' ); ?></h2>
						<div class="tab-panel__body">
							<?php echo wp_kses_post( $section['section_body'] ?? '' ); ?>
						</div>
					</section>
				<?php endforeach; ?>
			</div>
		<?php else : ?>
			<p class="manual-document__empty">
				<?php esc_html_e( 'This document has no sections yet.', 'lab-manual' ); ?>
			</p>
		<?php endif; ?>

		<?php if ( ! empty( $signatories ) ) : ?>
			<section class="manual-document__signatures signature-block">
				<h2 class="signature-block__title"><?php esc_html_e( 'Approvals', 'lab-manual' ); ?></h2>
				<ul class="signature-block__list">
					<?php foreach ( $signatories as $signatory ) : ?>
						<?php $image_id = lab_manual_resolve_attachment_id( $signatory['signatory_image'] ?? null ); ?>
						<li class="signatory">
							<?php if ( $image_id ) : ?>
								<div class="signatory__image">
									<?php echo wp_get_attachment_image( $image_id, 'medium' ); ?>
								</div>
							<?php endif; ?>
							<div class="signatory__details">
								<p class="signatory__name"><?php echo esc_html( $signatory['signatory_name'] ?? '' ); ?></p>
								<?php if ( ! empty( $signatory['signatory_title'] ) ) : ?>
									<p class="signatory__title"><?php echo esc_html( $signatory['signatory_title'] ); ?></p>
								<?php endif; ?>
							</div>
						</li>
					<?php endforeach; ?>
				</ul>
			</section>
		<?php endif; ?>
	</main>

	<?php
endwhile;

get_footer();
