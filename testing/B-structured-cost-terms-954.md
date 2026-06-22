# Structured event cost terms + rider (9.54) — unreleased

**Automated coverage added:** `test_edit_event.StructuredCostTermsTests` covers feature flag hiding/showing the cost_type field, terms word-count waiver when cost_type is set, and cost_type required validation error. Browser testing below covers UI interactions.

- [ ] `structured_cost_terms_enabled` flag in Site Settings: when off, cost_type dropdown is hidden on event edit
  RESULT:

- [ ] With flag on: cost_type dropdown appears; selecting "Film licence" reveals distributor, flat fee, VAT, percentage split, minimum guarantee sub-fields
  RESULT:

- [ ] Selecting "TBC": sub-fields hidden; terms word-count validation still active
  RESULT:

- [ ] Selecting any non-TBC cost type: terms word-count validation waived (form submits without filling terms)
  RESULT:

- [ ] Rider / hospitality notes field accepts free text; shown in event hub cost summary
  RESULT:

- [ ] Sound engineer name, fee, and "paid by" fields save correctly and appear in event hub
  RESULT:

- [ ] Technical notes field (AV/tech rider) saves independently of financial terms
  RESULT:

- [ ] Cost fields pre-populate from event template when flag is on
  RESULT:
