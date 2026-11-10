/**
 * Plain-language description of what each operator actually does to the pixels.
 *
 * Material-loss text mirrors `src/evaluation/matrix_synthesis.py`; review-prototype
 * text mirrors `scripts/build_damage_review_prototype.py`. Update both together.
 * These describe synthetic interventions only — never recovered historical content.
 */
export const DAMAGE_CHANGES: Record<string, string> = {
  "D2-01": "One closed hole with a slightly organic outline is centred on the selected writing region and never touches the page edge. Its size is calibrated to remove the target share of that region; the hole is made fully transparent and nothing is painted back in.",
  "D2-02": "One loss enters from a single page edge with an almost straight front. Its depth is calibrated to remove the target share of the selected writing region; removed pixels are made fully transparent.",
  "D2-03": "One loss enters from a single page edge with a ragged, multi-scale paper-edge front. Its depth is calibrated to remove the target share of the selected writing region; removed pixels are made fully transparent.",
  "D2-04": "Within a seeded patch, only dark ink pixels are replaced with a pale, blurred paper tone, so letter strokes break up while the surrounding parchment stays.",
  "D2-06": "A cloudy, translucent cream-coloured film with fine random texture is blended over a seeded patch of the writing area.",
  "D2-07": "A slightly slanted vertical strip of translucent amber is laid across the writing area, with darker edges where an aged tape border would be.",
  "D2-08": "About 240 small dark-brown spots of varying size and opacity are scattered over the writing area.",
  "D2-09": "A large, soft brown stain is blended into the writing area, with a slightly darker tide line along its outer edge.",
  "D2-10": "About 24 dark, gently wavy pen strokes of varying width are drawn horizontally across the writing area, over the existing text.",
  "D2-11": "Ink in a wide seeded patch is blended toward the page's own paper colour, in proportion to its darkness, so letters fade but remain in place.",
  "D2-12": "A seeded patch is rubbed toward a rough, mottled paper tone; ink there is lifted more strongly than the surrounding surface.",
  "D2-13": "Four soft-edged oval patches are blended toward a pale paper tone, imitating rubbed-out lines of text.",
  "D2-14": "The page is mirrored and its ink is printed back faintly in brown within a seeded patch — a proxy for text transferred from a facing page.",
  "D2-16": "Brown haloes are drawn around ink strokes within a seeded patch, imitating ink that has corroded into the surrounding support.",
  "D2-17": "The page is mirrored, blurred, and its ink is blended in as a soft brown shadow — a proxy for ink bleeding through from the other side.",
  "D2-18": "Two slanted fold lines cross the whole leaf. Each has a shaded side and a highlighted side; no pixels are removed.",
  "D2-19": "Each pixel row of the whole leaf is shifted in a gentle wave, and soft wave-shaped light and shadow is added to imitate cockled parchment.",
};
