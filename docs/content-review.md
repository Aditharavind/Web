# NAWA Global — content and design review

## Proposed positioning

**Oilfield & industrial supply**

**Supply that keeps industry moving.**

Oilfield components, maintenance essentials and safety products—sourced around your
specifications, quantities and delivery requirements.

This is a proposed corporate direction for management review. It is distinct from
Neo Smart's scientific positioning and retains NAWA Global's green identity.

## Content structure

- Home: positioning, company introduction, six capabilities, four reasons to work
  with NAWA Global, four sectors and an enquiry call to action.
- About: company narrative, mission, vision and six core values.
- Products & sourcing: six supply categories, example products, a four-stage
  procurement process and the information needed for specification-sensitive items.
- Catalogue: searchable products; a useful enquiry route while products are being prepared.
- Contact: direct email, telephone and WhatsApp, plus an RFQ checklist.

Editorial source: `app/core/content.py`. Public templates use shared icon and CTA partials.

## Mission

To help customers procure the right industrial products through careful requirement
review, clear communication and accountable order coordination.

## Vision

To become a preferred sourcing partner for energy and industry, recognised for
dependable relationships, practical expertise and lasting value.

## Values

Integrity, precision, safety awareness, accountability, partnership and practical value.
These are proposed principles, not assertions of accreditation or audited performance.

## Claims removed

The earlier site displayed an establishment year, brand counts, product statistics,
"authorized brands & partners", universal compliance claims and response-time promises.
They were not supported by supplied evidence. They are omitted from the revised pages.
No client names, certifications, project counts, foreign offices or guaranteed delivery
commitments have been introduced. Specific makes and authorization logos can be added
when management confirms the relevant relationships and logo use.

## Identity and contact details to confirm

The user confirmed the domain: **nawaglobalgtd.com**. The live domain could not be
retrieved during this review; the repository was the source for the supply categories.

The following details are carried from that repository and need management confirmation:

- Confirmed registered name: Nawa Global General Trading LLC SPC.
- Confirmed email: info@nawaglobalgtd.com.
- Confirmed primary telephone/WhatsApp: +971505464847.
- Confirmed secondary telephone/WhatsApp: +971506612605.
- Primary contact is highlighted with direct call/WhatsApp actions; the secondary is subordinate.
- Location: Mussafah, Abu Dhabi, United Arab Emirates (provide a full office address if desired).
- Product scope: confirm all six capability groups and examples are actually offered.

The header uses a proposed typographic wordmark and simple N device. Replace with the
approved vector logo when supplied. No official trademark artwork was available.

## Design system

Light-only interface, forest green accents, restrained brass details, white and pale
sage surfaces. Inter is used for body text and controls; Manrope for headings.
Fonts are served locally with font-display swap; Arial/sans-serif fallbacks remain available.
The corresponding font licenses are included under `app/static/fonts/`.
Icons and the decorative industrial illustration are local SVG, with no remote icon
library or stock photograph dependency. Icons are hidden from assistive technology
where accompanying text supplies their meaning. Motion respects reduced-motion settings.

## Release status

This is a review candidate. The contact page uses direct email/WhatsApp links while
direct enquiry channels are the confirmed approach. Publication and AWS deployment have not occurred.

## Validation

11 local tests pass. Browser checks at 1440, 768 and 390 px verify the five public
pages, no horizontal overflow, one main landmark and one H1 per page, working
mobile menu controls, and no local HTTP errors. Desktop and mobile screenshots
were reviewed separately and are excluded from the source tree. PostgreSQL/Redis production integration remains
a separate deployment check.

## Admin edit regression verification

The image-removal forms were nested inside the edit form. They now sit outside
the edit form and their individual buttons reference them with HTML form IDs.
Browser verification covers adding a product with an image, editing text/category/
specifications, appending images, removing an image, saving again, catalogue
updates and deleting the product. HTTP regression tests cover the same lifecycle
and verify that forms are not nested. Gallery limits count existing plus new images.

The obsolete contact POST handler and contact-form-only validation schema were
removed after confirmation that enquiries use WhatsApp/email directly.

The repository files and references were checked again. Existing database records
and uploads are not reset by this update. PostgreSQL/Redis and AWS-specific TLS,
backups and process configuration require verification on the selected target host;
they are not claimed as completed by these local browser/SQLite checks.
