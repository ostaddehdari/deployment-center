# ZohaOnline v0.4.0 — Hybrid Gravity Runtime Index Builder

This release restores the professional Gravity-Forms-style toolbox while keeping Runtime taxonomies as the canonical vocabulary source.

## Builder architecture
- Left collapsible toolbox with two tabs: Elements / Settings.
- Full field palette: text, textarea, rich text, number, boolean, email, phone, URL, date, time, datetime, select, searchable select, multi-select, radio, checkbox, tags, consent, file, reference, relation, repeater, group, duration, color, range, name, address, section, HTML, page break and hidden.
- Drag/drop and click-to-add.
- Field settings, width, required/search/index toggles, manual options and conditional logic.
- Choice fields can use Manual options or a real Runtime taxonomy.
- Runtime-bound fields expose the real taxonomy item manager (search/add/edit/deactivate/reactivate).
- Draft preview uses the same IndexRuntimePanel via schemaOverride.
- Publish activates the versioned form layout for the user runtime.

## Runtime architecture
The versioned index form is now the presentation/layout layer. Runtime taxonomies and terms remain the canonical vocabulary layer. Published form fields can bind to taxonomies using config.runtime.taxonomyCode.

Migration 180 performs the one-time bridge for the three system content types by seeding their active/draft system forms from the existing 98 runtime assignments.

No legacy source history is moved to GitHub; GitLab remains source of truth.
