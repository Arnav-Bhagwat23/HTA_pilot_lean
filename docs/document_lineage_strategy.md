# Document Lineage Strategy

## Purpose

This document defines how retrieved documents should be grouped into version lineages.

The lineage layer is the bridge between:

- raw retrieved documents
- timeline normalization
- schema backfilling

Without lineage grouping, the pipeline cannot safely decide whether two files are:

- different versions of the same artifact
- different document types in the same HTA process
- or unrelated files that happen to mention the same product

## Design Goal

The lineage system should answer:

- which documents belong to the same evolving artifact
- which document is the latest version in that artifact chain
- how versions should be ordered within a lineage

## Core Principle

Lineage should be conservative.

It is better to leave two documents in separate lineages than to incorrectly merge unrelated documents.

So the default behavior should be:

- only merge when the evidence is strong
- keep separate when uncertain

## Proposed Lineage Fields

Each normalized timeline document should eventually support these lineage fields.

### 1. `document_lineage_id`

Stable identifier for all versions of the same underlying document artifact.

Examples:

- one NICE guidance across versions
- one HAS `avis` chain
- one G-BA assessment artifact
- one AEMPS IPT chain

### 2. `version_rank`

Integer rank within the lineage.

Recommended convention:

- lower number = earlier version
- higher number = later version

### 3. `is_latest_version`

Boolean flag for the newest known version within the lineage.

### 4. `lineage_confidence`

Confidence label for the lineage assignment itself.

Recommended values:

- `strong`
- `moderate`
- `weak`

### 5. `lineage_basis`

Short label or note describing why the documents were grouped together.

Examples:

- `same_source_same_slug`
- `same_product_same_title_normalized`
- `same_report_code`
- `same_ipt_number`
- `same_psd_series`

## Minimum Matching Signals

To place documents into the same lineage, use a combination of these signals:

- same `source_id`
- same `country`
- same `document_family`
- same normalized product identity
- same or highly similar normalized title
- shared report code / IPT number / document series marker when available
- same or similar page URL path pattern

Lineage should not be based on product name alone.

## Normalization Inputs For Lineage

Before lineage grouping, normalize these fields:

- `source_id`
- `country`
- `product_name`
- `brand_name`
- `generic_name`
- `document_type`
- `document_stage`
- `document_family`
- `title`
- `page_url`
- `document_url`
- `publication_date`
- `revision_date`

The lineage step depends on the timeline normalization layer already being applied.

## Recommended Lineage Algorithm

### Step 1. Partition by Source

Do not attempt cross-source lineage first.

For example:

- a NICE document and an SMC document are not versions of the same artifact
- a HAS document and an AEMPS document are not versions of the same artifact

Initial grouping should always begin within:

- one `source_id`
- one `country`

### Step 2. Partition by Product Identity

Within each source, group only documents associated with the same normalized product identity.

Recommended keys:

- `brand_name`
- `generic_name`
- `match_term`

### Step 3. Build A Source-Specific Stable Key

Each source should define a first-pass lineage key.

Examples:

- NICE: normalized guidance URL slug or guidance ID
- SMC: advice page slug
- HAS: product history page + document family subtype
- G-BA: Nutzenbewertung page URL + document family subtype
- AIFA: result title pattern + embedded file naming series
- AEMPS: IPT number or normalized IPT title
- PBAC: product page title + PBAC meeting series

### Step 4. Separate Document Families Within A Source

Even within one product and source, different document families should stay separate.

Examples:

- HAS `avis` should not share a lineage with `transcription`
- G-BA `IQWiG assessment` should not share a lineage with `Modul 3`
- AIFA reimbursement PDFs should not share a lineage with registry ZIPs

### Step 5. Order Versions Chronologically

Within a lineage, order versions using:

1. `publication_date`
2. `revision_date`
3. fallback lexical cues in title or version label

Latest version becomes:

- `is_latest_version = true`

## Country-Specific Lineage Rules

Because sources behave differently, lineage should start with explicit source rules.

### United Kingdom

#### NICE

Strong lineage signals:

- same guidance page URL
- same NICE guidance code if present in title or URL

Likely lineage key:

- `nice_uk::<guidance_slug_or_code>`

#### SMC

Strong lineage signals:

- same medicine advice page URL
- same brand/generic core title

Likely lineage key:

- `smc_uk::<advice_slug>`

### France

#### HAS

Lineages should be separated by document subtype.

Suggested lineage families:

- `avis`
- `summary`
- `transcription`
- economic opinion if later retained

Likely lineage key:

- `has_france::<product_page_or_history_id>::<document_subtype>`

### Germany

#### G-BA

Lineage should not merge all PDFs on a Nutzenbewertung page together.

Separate at least:

- IQWiG assessment
- dossier modules
- annexes
- hearing/protocol materials

Likely lineage key:

- `gba_germany::<nutzenbewertung_id>::<document_series>`

### Italy

#### AIFA

Separate:

- reimbursement/pricing documents
- registry documents
- result-page procedural notices

Likely lineage signals:

- repeated determination number
- repeated registry series naming
- repeated result title pattern

Likely lineage key:

- `aifa_italy::<normalized_series_key>::<document_family>`

### Spain

#### AEMPS

This should be the cleanest lineage system.

Strong lineage signals:

- IPT number in the PDF filename
- normalized IPT title

Likely lineage key:

- `aemps_spain::<ipt_number_or_normalized_title>`

### Australia

#### PBAC

Strong lineage signals:

- same product page title
- same PSD series label
- same meeting chain if revisions exist

Likely lineage key:

- `pbac_australia::<normalized_product_title>`

## Title Normalization For Lineage

To support grouping, build a normalized title string that:

- lowercases
- strips punctuation
- removes repeated whitespace
- removes obvious file-extension noise
- removes generic words like `pdf`, `download`, `summary document` only when they are not semantically important

Do not over-normalize document subtype words that affect lineage, such as:

- `summary`
- `transcription`
- `avis`
- `modul`
- `annex`
- `iqwig`
- `ipt`
- `psd`

## Signals That Should Increase Lineage Confidence

Examples of strong signals:

- exact same stable page URL path
- same source-specific report code
- same IPT number
- same document family and normalized title

Examples of moderate signals:

- same product + very similar title + close publication dates

Examples of weak signals:

- same product name only
- same therapeutic area only

## Signals That Should Block A Merge

Do not merge when:

- `source_id` differs
- `document_family` differs in a meaningful way
- `document_stage` clearly differs in artifact type
- source-specific series identifiers conflict
- one file is clearly a supporting annex and the other is a final opinion

## Recommended First Implementation

The first lineage implementation should only support:

- source-local grouping
- conservative source-specific keys
- `document_lineage_id`
- `version_rank`
- `is_latest_version`
- `lineage_confidence`
- `lineage_basis`

Do not try fuzzy clustering across unrelated sources in the first pass.

## Example Lineage Outcomes

### Example 1: AEMPS IPT Revisions

Two AEMPS documents:

- same IPT number
- same core title
- different dates

Result:

- same lineage
- earlier one gets lower `version_rank`
- newest one gets `is_latest_version = true`

### Example 2: HAS Avis vs Summary

Two HAS files:

- same product
- same meeting period
- one is `avis`
- one is `summary`

Result:

- separate lineages
- same broader product context, but not the same artifact chain

### Example 3: G-BA IQWiG vs Modul 3

Two G-BA files:

- same Nutzenbewertung page
- one is `Nutzenbewertung IQWiG`
- one is `Modul 3`

Result:

- separate lineages

## Relationship To Backfill

Backfill must run within a lineage, not across all product documents.

That means:

- find lineage first
- then backfill only using earlier versions in the same lineage

This prevents:

- filling an `avis` from a `summary`
- filling a final decision from an annex
- filling an IPT from an unrelated product page

## Recommended Next Step

After this design, the first code implementation should:

1. add lineage fields to the normalized timeline model
2. implement source-specific lineage key derivation
3. create a function that groups normalized documents into lineages
4. assign `version_rank` and `is_latest_version`
5. only then apply field-level backfill
