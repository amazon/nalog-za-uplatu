# QR Uplatnica — MVP Application Description

## 1. Product overview

**Working product name:** QR Uplatnica
**Proposed domain:** `qruplatnica.rs`, subject to availability
**Product type:** Static, installable web application
**Primary market:** Serbia
**Primary language:** Serbian Latin, with full support for Serbian Cyrillic input
**Backend:** None in the MVP
**Server-side database:** None
**Local storage:** IndexedDB in the user’s browser
**Installation model:** Progressive Web App

QR Uplatnica is a privacy-oriented web application for creating Serbian payment slips containing NBS IPS-compatible QR codes.

Users can prepare one or many payment slips, print up to three slips on a single A4 page, create compact sharing links, save frequently used recipients and templates locally, generate recurring monthly payment drafts, and create parameterized template links for use in Google Sheets, Excel, CRM systems, and other data-management tools.

The application does not process payments. It prepares payment instructions that users can print, share, or scan with a compatible banking application.

---

## 2. Product positioning

QR Uplatnica should not be positioned as merely another QR code generator.

Its core proposition is:

> Create, reuse, print, and share Serbian payment slips—individually or in batches.

Its main differentiators are:

* multiple payment slips in one workspace;
* up to three printable slips per A4 page;
* one sharing link containing multiple payment slips;
* local recipient and template storage;
* recurring payment-slip generation;
* spreadsheet and CRM template links;
* offline operation;
* no account requirement;
* no server-side storage of payment data.

A suitable short description is:

> Napravite, sačuvajte, odštampajte i podelite uplatnice sa IPS QR kodom.

A longer description is:

> Besplatan alat za pripremu pojedinačnih i grupnih uplatnica sa IPS QR kodom. Radi lokalno u pregledaču, podržava štampanje do tri uplatnice po A4 strani, čuvanje šablona i kreiranje linkova za deljenje.

---

## 3. Problem being solved

Existing payment-slip generators primarily address a simple scenario:

1. fill in one payment form;
2. generate one QR code;
3. download or print the result.

Real users frequently have more complex needs:

* an accountant prepares several payments for one client;
* a landlord sends rent and utility instructions every month;
* a school sends several payment requests to each parent;
* a sports club prepares monthly membership slips;
* a building manager distributes maintenance-payment instructions;
* a family member prepares multiple slips for an older relative;
* an organization keeps recipients in a spreadsheet or CRM rather than in a dedicated payment application.

QR Uplatnica addresses these workflows without becoming a payment processor, accounting platform, or financial institution.

---

## 4. Target users

### 4.1 Individual users

Individuals who occasionally or repeatedly prepare:

* utility-payment slips;
* rent payments;
* school payments;
* membership fees;
* taxes and administrative fees;
* payments for family members.

Their priorities are simplicity, privacy, correct QR generation, and printable output.

### 4.2 Accountants and bookkeepers

Users who regularly prepare multiple payment instructions for clients.

Their priorities are:

* reusable templates;
* batch creation;
* fast duplication and editing;
* spreadsheet integration;
* compact A4 printing;
* exporting and sharing groups of slips.

### 4.3 Landlords and property managers

Users who repeatedly distribute payment instructions to tenants.

Their priorities are:

* recurring monthly templates;
* recipient groups;
* different amounts or reference numbers per tenant;
* one-click preparation of monthly drafts;
* links that can be sent through email or messaging applications.

### 4.4 Schools, clubs, and associations

Organizations collecting:

* tuition;
* meals;
* excursions;
* memberships;
* equipment fees;
* insurance;
* donations.

Their priorities are generating several payment requests for each person and managing data through Google Sheets, Excel, or a CRM.

### 4.5 Building managers

Users who distribute regular maintenance or common-expense instructions.

Their priorities are monthly generation, reference-number handling, spreadsheet integration, and batch distribution.

---

## 5. Product principles

### 5.1 Local-first

Payment data remains in the user’s browser unless the user deliberately exports or shares it.

### 5.2 No mandatory registration

The core application must work without an account, email address, phone number, or login.

### 5.3 Review before payment

The application creates payment instructions but cannot guarantee that a recipient, account number, or payment request is legitimate.

Users must be encouraged to review the following fields inside their banking application before confirming a payment:

* recipient;
* recipient account;
* amount;
* payment purpose;
* model;
* reference number.

### 5.4 Progressive complexity

A first-time user should be able to create one slip immediately.

Advanced functionality should become visible only when relevant:

* multiple slips;
* saved templates;
* recurring schedules;
* spreadsheet integration;
* import and export.

### 5.5 Portable data

Users should be able to export their local data and move it between browsers or devices.

### 5.6 Standards-oriented implementation

The generated IPS QR payload and printable output must follow the applicable Serbian payment-slip and IPS QR format requirements.

---

# 6. MVP scope

The MVP includes the following functional areas:

1. payment-slip editor;
2. IPS QR generation;
3. multi-slip workspace;
4. A4 printing;
5. compact sharing links;
6. local recipients and templates;
7. recurring local payment schedules;
8. spreadsheet and CRM template links;
9. import and export;
10. offline PWA installation.

The MVP does not include:

* user accounts;
* backend storage;
* automatic email or SMS delivery;
* verified senders;
* ECDSA signatures;
* server-side scheduling;
* native Android development;
* Electron or another Windows desktop wrapper;
* payment initiation or bank-account access;
* accounting-system synchronization.

---

# 7. Main application areas

## 7.1 Payment-slip editor

The editor is the primary screen of the application.

It must support all fields required to produce a Serbian payment slip and IPS QR payload, including:

* payer name;
* payer address;
* payer place;
* payment purpose;
* recipient name;
* recipient address, where applicable;
* recipient place, where applicable;
* payment code;
* currency;
* amount;
* recipient account number;
* model;
* reference number.

The exact field structure must match the current IPS QR and Serbian payment-slip specifications implemented by the application.

### Editor behaviour

The editor should provide:

* immediate validation;
* normalized formatting;
* clear error messages;
* a live printable preview;
* a live QR preview;
* keyboard-friendly navigation;
* sensible field ordering;
* copy and paste support;
* preservation of Serbian diacritics and Cyrillic text.

Invalid input must not silently produce an apparently valid QR code.

### Validation examples

The application should detect:

* missing required fields;
* malformed recipient accounts;
* unsupported payment codes;
* invalid amount formats;
* invalid model values;
* reference numbers incompatible with the selected model;
* values exceeding IPS QR length limits;
* characters unsupported by the selected encoding.

Validation messages should identify the exact field and explain what the user should correct.

---

## 7.2 IPS QR code generation

The application generates an IPS QR code from the validated payment-slip fields.

The QR code must:

* use the correct payload structure;
* preserve required character encoding;
* remain readable when printed;
* include sufficient quiet space;
* scale without becoming blurred;
* be generated locally;
* never require an external QR-generation service.

The application should provide a visual status:

* **QR code valid**
* **QR code cannot be generated**
* **Check the highlighted fields**

The QR code should update automatically when valid source fields change.

---

## 7.3 Multi-slip workspace

Users can add multiple payment slips to one workspace.

Each slip appears as a card containing:

* recipient;
* amount;
* payment purpose;
* reference number;
* validation status;
* QR thumbnail;
* actions.

Available actions:

* edit;
* duplicate;
* delete;
* move up;
* move down;
* select or deselect;
* save as template;
* create another slip from this one.

The workspace should provide a summary:

* total number of slips;
* number of valid slips;
* number containing errors;
* total amount, when all slips use the same currency.

The user must be warned before printing or sharing a collection containing invalid slips.

### Practical limits

The format should technically support many slips, but the interface may warn users when a bundle becomes very large.

For example:

> The sharing link is becoming long. Consider splitting this collection into several links.

The application should not impose an unnecessarily low fixed limit unless required by browser or QR constraints.

---

# 8. Printing

## 8.1 Print layouts

The MVP must support:

* one payment slip per A4 page;
* two payment slips per A4 page;
* three payment slips per A4 page;
* automatic pagination for larger collections.

The default should be three slips per page when the printable design remains compliant and readable.

Users should be able to choose:

* slips per page;
* page orientation, if more than one orientation is supported;
* selected slips or all slips;
* whether to include QR codes;
* whether to include cutting guides;
* whether to include a small generation timestamp.

## 8.2 Print preview

Before opening the browser print dialog, the user should see a dedicated preview showing:

* page boundaries;
* slip placement;
* QR dimensions;
* expected page count;
* any clipped or overflowing text.

The application should use print-specific CSS rather than relying on screenshots or rasterized pages.

Text and QR codes should remain sharp on standard office printers.

## 8.3 Printable warnings

Application navigation, buttons, helper messages, and advertisements must never appear in the printed output.

The printable payment slip should contain only the required payment information and any deliberately enabled auxiliary information.

---

# 9. Sharing links

## 9.1 Purpose

A sharing link allows another person to open one or many prepared payment slips without the sender uploading them to a server-side database.

Typical use cases:

* sending a payment request through a messaging application;
* sending several school-payment instructions in one link;
* sharing rent and utility slips;
* preparing slips for a relative;
* transferring a temporary workspace to another device.

## 9.2 Encoding format

The sharing payload should:

* be serialized deterministically;
* use an explicit format version;
* use the existing custom zstd-inspired compression;
* use the custom Serbian vocabulary;
* be encoded safely for use in a URL;
* be stored after the URL fragment marker `#`.

Conceptual form:

```text
https://qruplatnica.rs/#s=<encoded-payload>
```

The fragment should not ordinarily be transmitted to the web server.

## 9.3 Security description

The application must not describe the custom compressed format as encryption.

Suitable wording:

> Podaci u linku koriste kompaktan format aplikacije i nisu neposredno čitljivi. Link ipak treba čuvati kao i samu uplatnicu, jer svako ko ima link može otvoriti podatke.

The application should explain that:

* the link may contain personal or financial information;
* anyone possessing the complete link can open it;
* forwarded links remain usable;
* the format reduces readability but is not a cryptographic confidentiality mechanism.

## 9.4 Shared-link view

Opening a sharing link should display:

* a concise bundle summary;
* all included payment slips;
* validation status;
* printable previews;
* QR codes;
* the ability to print selected or all slips;
* the ability to import the slips into the local workspace.

The shared view should not automatically save anything to IndexedDB.

The recipient must explicitly choose:

> Save to my templates

or:

> Open in workspace

---

# 10. Local recipient and template database

## 10.1 Storage technology

The application should use IndexedDB for structured local data.

The database remains entirely inside the browser profile.

No local records are sent to the application server.

## 10.2 Saved payment recipients

A saved payment recipient can contain:

* name;
* address;
* place;
* recipient account;
* default payment code;
* default model;
* default payment purpose;
* tags;
* user notes.

Recipient account numbers should be displayed in a consistent normalized format.

## 10.3 Saved payment templates

A payment template contains a reusable combination of:

* payer defaults;
* payment recipient;
* payment purpose;
* amount or amount rule;
* payment code;
* currency;
* model;
* reference number or reference rule;
* recurrence settings;
* tags;
* user notes.

A recipient and a template are separate concepts.

One recipient may have several templates, such as:

* monthly membership;
* annual registration;
* equipment fee;
* donation.

## 10.4 Search and organization

Users should be able to:

* search by recipient name;
* search by account number;
* search by payment purpose;
* filter by tags;
* sort by most recently used;
* mark templates as favourites;
* duplicate templates;
* archive unused templates.

## 10.5 Local-data notice

The application should clearly state:

> Saved recipients and templates are stored only in this browser. Clearing browser data or changing devices may remove them unless you create a backup.

---

# 11. Recurring payment templates

## 11.1 Purpose

Recurring templates help users prepare repeated payments without maintaining a server-side scheduler.

Supported recurrence options in the MVP:

* monthly;
* every two months;
* quarterly;
* annually;
* custom month interval.

A template may contain:

* generation day;
* payment due day;
* default amount;
* month-dependent payment purpose;
* reference-number rule;
* active-from date;
* optional end date.

## 11.2 Local due-payment dashboard

When the user opens the application, it checks local templates and displays due drafts.

Example:

> 5 uplatnica treba pripremiti za avgust 2026.

Actions:

* generate all;
* review individually;
* skip this period;
* postpone;
* mark as already handled.

The application does not silently send or print anything.

## 11.3 Draft-first workflow

Recurring schedules generate drafts, not final distributed payment requests.

The user must review:

* recipient account;
* amount;
* payment purpose;
* reference number;
* due date.

This prevents outdated data from being distributed automatically.

## 11.4 No guaranteed background execution

The MVP must not promise that the browser will wake up and perform a task on a particular date.

Recurring logic is evaluated when the user opens or activates the application.

Optional local notifications may be added only where browser support is reliable, but the application must remain fully usable without them.

---

# 12. Template links for Sheets, Excel, and CRMs

## 12.1 Purpose

Template links allow users to keep customer, tenant, pupil, member, or invoice data in an existing system while using QR Uplatnica to render the final payment slip.

Supported systems in the MVP:

* Google Sheets;
* Microsoft Excel;
* generic CRM URL templates;
* any system that can generate a URL from record fields.

No direct API or OAuth integration is required.

## 12.2 Template field types

Each field in an integration template can have one of four behaviours.

### Locked

The value is defined by the template and cannot be replaced by external row data.

Typical locked fields:

* recipient name;
* recipient account;
* payment code;
* model.

### Variable

The value must be supplied by the spreadsheet or CRM.

Typical variable fields:

* payer name;
* payer address;
* amount;
* membership number;
* invoice number;
* reference number.

### Editable

The external system can provide an initial value, but the user may change it after opening the link.

### Calculated

The application derives the value from other supplied fields according to a supported rule.

Examples:

* payment purpose containing the current month;
* reference constructed from a customer identifier;
* amount derived from base amount and quantity.

Calculated fields in the MVP should use a limited, safe rule system rather than arbitrary JavaScript expressions.

## 12.3 Template-link structure

Conceptual structure:

```text
https://qruplatnica.rs/#t=<template>&d=<record-data>
```

Where:

* `t` contains the template definition;
* `d` contains the values for one spreadsheet or CRM record.

The format must include:

* version;
* template definition;
* allowed variable fields;
* field constraints;
* provided data values.

External data must never be allowed to override locked fields.

## 12.4 Integration wizard

The application should provide a guided workflow:

1. Create or choose a payment template.
2. Mark each field as locked, variable, editable, or calculated.
3. Assign short integration names to variable fields.
4. Select the target system.
5. Map fields to columns or CRM placeholders.
6. Generate a ready-to-use formula or URL template.
7. Test the generated link with example data.

## 12.5 Google Sheets output

The wizard should produce:

* suggested column headers;
* a template prefix;
* a ready-to-paste `HYPERLINK` formula;
* an example first data row;
* instructions for filling the formula down.

Example conceptual output:

```excel
=HYPERLINK(
  $M$1
  & "&payer=" & ENCODEURL(A2)
  & "&amount=" & ENCODEURL(F2)
  & "&reference=" & ENCODEURL(G2),
  "Uplatnica"
)
```

The actual generated formula must use the application’s final payload format rather than necessarily exposing readable field names.

## 12.6 Excel output

The wizard should generate an equivalent Excel formula using functions available in the selected Excel version.

The application should warn users when a function is not available in older versions.

## 12.7 Generic CRM output

The wizard should generate a URL pattern such as:

```text
https://qruplatnica.rs/#t=...&d={encoded_record}
```

or a placeholder-based form such as:

```text
https://qruplatnica.rs/#...{customer_name}...{amount}...{reference}
```

The user can choose placeholder syntax appropriate for the target system.

The MVP does not need custom connectors for individual CRM products.

---

# 13. Import and export

## 13.1 Full local backup

Users must be able to export:

* saved recipients;
* saved templates;
* recurrence settings;
* tags;
* favourites;
* application preferences.

The export should use a versioned application format.

## 13.2 Import

Import should:

* validate the file before modifying local data;
* show a summary;
* detect duplicates;
* allow merge or replace;
* report skipped or invalid records;
* never execute embedded code.

## 13.3 Backup protection

The minimum MVP may support an unencrypted local backup with a clear warning.

Password-protected encrypted backup is strongly desirable and should be implemented within the MVP if it does not delay the core release.

When encryption is supported:

* encryption happens locally;
* the password is never transmitted;
* authenticated encryption is used;
* password loss makes the backup unrecoverable.

## 13.4 CSV import

Basic CSV import may be included for batch slip generation.

The user should map columns to payment fields through an import wizard.

CSV import does not automatically save every row as a permanent recipient unless the user explicitly selects that option.

---

# 14. Progressive Web App

## 14.1 Installation

The application should be installable on:

* Android;
* Windows through compatible browsers;
* Linux desktop browsers;
* other PWA-capable platforms.

It should include:

* web application manifest;
* application icons;
* maskable icon;
* standalone display mode;
* theme metadata;
* service worker.

## 14.2 Offline operation

After the initial successful load, core functionality should work offline:

* opening the application;
* editing slips;
* generating QR codes;
* printing;
* using saved recipients;
* using saved templates;
* generating local recurring drafts;
* importing previously generated links.

Network access may be required for:

* first installation;
* application updates;
* optional documentation;
* future server-backed features.

## 14.3 Service-worker caching

The service worker should cache only application assets required for offline execution.

It should not indiscriminately cache:

* shared payloads;
* personal form submissions;
* imported data;
* user-generated documents;
* future account API responses.

## 14.4 Updates

When a new application version is available, the user should receive a clear notification:

> Nova verzija aplikacije je dostupna.

The user should be able to reload safely without losing unsaved work.

---

# 15. User experience

## 15.1 First-use experience

The landing screen should immediately present the payment-slip form.

Primary actions:

* Create payment slip
* Add another slip
* Print
* Share

Secondary actions:

* Saved recipients
* Templates
* Recurring payments
* Spreadsheet integration
* Import

The application should not force the user through onboarding before they can create a slip.

## 15.2 Suggested navigation

Desktop navigation:

* Workspace
* Templates
* Recipients
* Recurring
* Integrations
* Import/Export
* Help

Mobile navigation may use a compact bottom bar or menu.

## 15.3 Progressive disclosure

Advanced fields and features should not overload the basic form.

Examples:

* show recurrence options only after selecting “Save as recurring template”;
* show integration settings only inside the integration wizard;
* show print-layout controls only in print preview;
* show compression details only in technical help.

## 15.4 Empty states

Useful empty-state examples:

> Nemate sačuvane primaoce. Sačuvajte primaoca iz prve uplatnice da biste ga sledeći put brže izabrali.

> Nema dospelih ponavljajućih uplatnica.

> Dodajte još jednu uplatnicu da biste napravili grupni link.

## 15.5 Destructive actions

Deleting a template, recipient, or complete local database must require confirmation.

The application should support undo where practical.

---

# 16. Privacy and security

## 16.1 Privacy statement

The application should make the local-first model understandable:

> Podaci koje unesete obrađuju se lokalno u vašem pregledaču. Ne šalju se na server, osim kada sami podelite link ili koristite buduću mrežnu funkciju koja to izričito zahteva.

## 16.2 Shared links

The user must be warned that:

* anyone with the link can open the contained slips;
* compression is not encryption;
* the link may remain in browser history or messaging history;
* personal information should not be shared unnecessarily.

## 16.3 Third-party resources

The production application should avoid third-party scripts where possible.

Particularly avoid loading third-party analytics, font scripts, QR generators, or trackers on pages containing payment data.

If analytics are added, they should be privacy-preserving and should never capture:

* URL fragments;
* account numbers;
* payer names;
* recipient names;
* amounts;
* reference numbers;
* entered form values.

## 16.4 Content security

The application should use a restrictive Content Security Policy.

User-provided text must never be inserted as executable HTML.

Imported files and link payloads must be treated as untrusted data.

## 16.5 Dependency security

QR generation, compression, serialization, and IndexedDB libraries should be:

* minimal;
* pinned to known versions;
* reviewed;
* included locally where practical;
* covered by automated tests.

---

# 17. Trust and disclaimers

The footer and help section should clearly state:

> QR Uplatnica is an independent application and is not affiliated with or endorsed by the National Bank of Serbia.

The application should not claim:

* that a payment recipient is legitimate;
* that the recipient owns the displayed account;
* that opening a link proves who created it;
* that a compressed link is encrypted;
* that a generated payment will be accepted by every bank;
* that the application performs or guarantees a payment.

Suggested confirmation message near the QR code:

> Pre potvrde plaćanja proverite primaoca, račun, iznos i poziv na broj u aplikaciji svoje banke.

---

# 18. Accessibility

The MVP should meet practical WCAG-oriented accessibility requirements.

It should include:

* complete keyboard navigation;
* visible focus indicators;
* semantic form labels;
* error messages linked to fields;
* sufficient contrast;
* scalable text;
* screen-reader descriptions;
* no reliance on colour alone;
* accessible print-preview controls;
* large mobile touch targets.

QR codes should be accompanied by the human-readable payment details.

---

# 19. Technical architecture

## 19.1 Frontend

The application can be implemented as a static frontend using:

* HTML;
* CSS;
* TypeScript or JavaScript;
* a lightweight frontend framework or vanilla components;
* client-side routing where necessary.

The architecture should not require server-side rendering or an application backend.

## 19.2 Main modules

Suggested module boundaries:

* payment-slip domain model;
* field validation;
* IPS payload encoder;
* QR renderer;
* printable-slip renderer;
* collection workspace;
* share-link codec;
* template-link codec;
* local IndexedDB repository;
* recurrence engine;
* import/export engine;
* spreadsheet formula generator;
* PWA service worker;
* application settings.

The IPS encoder and validator should remain independent of the UI.

## 19.3 Versioning

All persistent and portable formats must include versions:

* IndexedDB schema version;
* exported backup version;
* share-link payload version;
* template-link payload version;
* recurrence-rule version.

The application should retain decoders and migration logic for previously published formats wherever practical.

A link created by an older version should not stop working merely because a new release changes internal models.

---

# 20. Core data model

## PaymentSlip

```text
id
payer
paymentPurpose
recipient
paymentCode
currency
amount
recipientAccount
model
referenceNumber
createdAt
updatedAt
```

## Recipient

```text
id
name
address
place
account
defaultPaymentCode
defaultModel
defaultPurpose
tags
notes
createdAt
updatedAt
lastUsedAt
```

## PaymentTemplate

```text
id
name
recipientId
payerDefaults
paymentFields
fieldRules
tags
isFavourite
recurrence
createdAt
updatedAt
lastUsedAt
```

## Recurrence

```text
enabled
frequency
interval
generationDay
dueDay
startDate
endDate
lastGeneratedPeriod
```

## IntegrationTemplate

```text
id
name
basePaymentTemplate
fieldDefinitions
calculationRules
targetSystem
formatVersion
createdAt
updatedAt
```

## IntegrationFieldDefinition

```text
field
mode: locked | variable | editable | calculated
externalName
defaultValue
validation
calculationRule
```

---

# 21. Primary user flows

## 21.1 Create and print one slip

1. User opens the application.
2. User fills in the payment form.
3. Application validates the fields.
4. QR code and slip preview appear.
5. User selects Print.
6. Application shows print preview.
7. Browser print dialog opens.

## 21.2 Create and share several slips

1. User creates the first slip.
2. User selects Add another.
3. User creates or duplicates additional slips.
4. Workspace shows all slips and validation results.
5. User selects Share.
6. Application compresses the collection locally.
7. Application generates one fragment-based URL.
8. User copies or shares the link.

## 21.3 Save and reuse a recipient

1. User creates a slip.
2. User selects Save recipient.
3. User assigns optional tags.
4. On a future slip, user searches for the recipient.
5. Application fills the saved recipient fields.
6. User enters only the changing payment details.

## 21.4 Create a recurring template

1. User creates a valid slip.
2. User selects Save as recurring template.
3. User names the template.
4. User configures monthly recurrence.
5. Application stores the rule locally.
6. In the next applicable period, the dashboard offers a draft.
7. User reviews and generates the slip.

## 21.5 Generate a Google Sheets formula

1. User chooses a saved payment template.
2. User opens Spreadsheet integration.
3. User marks recipient account as locked.
4. User marks payer name, amount, and reference as variable.
5. User maps those fields to spreadsheet columns.
6. Application creates a ready-to-paste formula.
7. User pastes it into Google Sheets.
8. Each spreadsheet row produces an Uplatnica link.

---

# 22. MVP acceptance criteria

The MVP is ready for public release when all of the following are true.

## Payment generation

* A user can create a valid Serbian payment slip.
* A correct IPS QR code is generated locally.
* Invalid fields prevent final generation.
* Serbian Latin and Cyrillic text are preserved correctly.

## Multiple slips

* A user can create, duplicate, reorder, edit, and delete slips.
* A user can print several selected slips.
* Up to three slips fit correctly on an A4 page.
* Page breaks do not split individual slips.

## Sharing

* One link can contain multiple slips.
* Opening the link restores the collection reliably.
* The payload is stored in the URL fragment.
* Old format versions are detected.
* Corrupted payloads produce a safe, understandable error.

## Local storage

* Recipients and templates persist after reloading.
* Users can search and organize saved records.
* Users receive a warning about browser-local storage.
* Full export and import work reliably.

## Recurrence

* Monthly recurring templates can be created.
* Due drafts are shown when the application is opened.
* Duplicate generation for the same period is prevented or clearly warned about.
* No payment slip is sent automatically.

## Integrations

* Users can create locked and variable fields.
* Spreadsheet values cannot override locked fields.
* The application generates a usable Google Sheets formula.
* The application generates a usable Excel formula or clearly documents version limitations.
* A generic CRM URL template can be produced.

## PWA

* The application is installable.
* Core features work offline after initial installation.
* Updates do not destroy unsaved local work.
* The application works responsively on mobile and desktop.

## Privacy

* No payment fields are transmitted during ordinary local use.
* Third-party scripts cannot receive URL fragments or entered values.
* The privacy statement accurately describes application behaviour.
* The interface does not describe compression as encryption.

---

# 23. Features explicitly deferred beyond the MVP

## Verified senders

A future backend may verify:

* email addresses;
* phone numbers;
* organizations;
* representatives;
* recipient accounts.

Verification levels must describe exactly what was verified.

## Cryptographic signatures

Future signed links may include:

* issuer ID;
* verification level;
* issue time;
* expiration;
* payload hash;
* signing-key identifier;
* ECDSA signature.

Signed templates and signed completed payment requests must be treated as different trust levels.

## Automatic distribution

A future professional service may support:

* server-side recurring schedules;
* automatic email delivery;
* delivery history;
* revocation;
* expiration;
* failed-delivery notifications;
* audit logs.

This requires accounts, a backend, and server-side storage.

## Native applications

A dedicated Android app should be considered only when native capabilities provide meaningful value.

A Play Store wrapper around the PWA may be added later.

An Electron application is not planned unless genuine desktop-only requirements emerge.

## Direct integrations

Future integrations may include:

* Google Sheets add-on;
* Excel add-in;
* accounting software plugins;
* CRM-specific connectors;
* REST API;
* webhook-based generation;
* bulk signing API.

They should be developed only after the generic template-link workflow demonstrates demand.

---

# 24. Recommended launch version

The first public release should communicate three clear capabilities:

## Create

Generate one or many Serbian payment slips with IPS QR codes.

## Print

Print up to three slips per A4 page.

## Share

Send one compact link containing one or many payment slips.

Saved templates, recurring drafts, and spreadsheet integration should be presented as productivity features, not as prerequisites for using the application.

Suggested homepage structure:

1. Immediate payment-slip editor
2. Add another slip
3. Print or share
4. Saved locally
5. Recurring templates
6. Works with Sheets, Excel, and CRMs
7. Privacy explanation
8. Independent-service disclaimer

---

# 25. MVP success indicators

Without collecting payment data, the application can measure anonymous product events such as:

* application opened;
* slip successfully generated;
* multi-slip workspace used;
* print preview opened;
* sharing link generated;
* template saved;
* recurring template created;
* spreadsheet formula generated;
* application installed as a PWA.

Analytics must not contain entered field values, full URLs, URL fragments, account numbers, amounts, names, or references.

Useful qualitative signals include:

* repeated use of saved templates;
* organizations requesting bulk workflows;
* users asking for verified senders;
* demand for automatic email distribution;
* demand for spreadsheet examples;
* demand for organization accounts;
* users installing the PWA rather than returning only once.

The MVP should be considered validated when users repeatedly return to prepare batches or recurring slips, rather than using it only as a one-time QR generator.

