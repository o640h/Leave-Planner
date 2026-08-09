# Design references

`leave-planner-dashboard-concept.png` is the first generated visual exploration from 2026-08-06. It is retained as design history, but its rounded light treatment was superseded by the operator's preferred dark, technical direction.

The active source palette is recorded directly in `frontend/src/styles.css`: solid layered charcoal surfaces, centrally adjustable low-opacity borders and focus edges, the compact light-weight Montserrat variable interface face, and semantic accent/nominal/warning colours. The signature precision-instrument treatment uses a clean shadowed navigation rail, flat single-pixel controls, framed status icons, compact two-letter consultant monograms, precise dividers, and controlled shadows. Avoid navigation textures/grids, clipped borders, decorative gradients, concentric identity rings, datum marks, or workspace grids. Interface code should remain code-native and accessible; do not embed the concept image in the product.

## Dark Direction Explorations

- `leave-planner-directions-dense-abc.png` records three early dark concepts. They were rejected as too dense and card-oriented, but remain useful design history.
- `leave-planner-quiet-grid.png` explores a typography-led consultant directory with an open table and minimal summary figures.
- `leave-planner-split-workspace.png` explores a consultant-first workspace with a persistent directory and a flat record inspector.
- `leave-planner-wallchart-canvas.png` explores the team wallchart as the application's main planning surface.
- `leave-planner-planning-calendar-concept.png` refines that wallchart into the planned shared
  calendar surface: public holidays remain visible in the time grid, while a right-hand drawer
  previews and saves one leave booking without hiding the wider team context.
- `leave-planner-desktop-workspace-v2.png` is the active 1440×900 consultant-workspace reference. It corrects the undersized, top-heavy browser composition by defining a deliberate desktop frame, a factual setup overview, and two full-height configuration panels.

These images are directional mockups, not exact interface specifications. Retain the palette and visual principles while implementing controls, copy, calculations, and accessibility as code-native application features.

## Approved Composite Direction

The application does not choose one mockup exclusively. It combines their strongest roles:

1. `leave-planner-split-workspace.png` defines the default consultant workspace: global navigation, a persistent consultant selector, and the selected consultant's information and editing surface.
2. `leave-planner-quiet-grid.png` defines the darker charcoal balance and restrained use of muted gold for dates. Its open table treatment can support a future team overview or directory view.
3. `leave-planner-wallchart-canvas.png` defines a separate wallchart page reached from primary navigation.

All three pages must share one token system and interaction language. Cyan is for selection and primary actions, muted gold is for dates and planned/attention states, and green is for confirmed positive states. Do not turn these directions into three independently styled dashboards.

The global navigation follows the mockups' narrow icon-only rail rather than displaying numbered text links or an `LP` monogram. Short creation flows open in compact modal dialogs; the large consultant workspace is reserved for selected-record information rather than oversized forms.

The implemented consultant page is a bounded desktop workspace: the icon rail and consultant directory stay stable while the selected consultant's content scrolls independently. Leave-year and job-plan information sit in sibling panels so the current configuration can be read at a glance. Responsive behaviour follows the actual content-pane width, not only the outer browser width, which keeps the same structure usable in the planned resizable desktop window. Future dashboard panels must be backed by real slice data rather than decorative placeholder figures.

The preferred initial desktop window is 1440×900. On larger development monitors the browser preview centres that exact frame rather than stretching small controls across the full viewport; at or below the target dimensions it fills the available window. The launcher should use the same initial size while allowing the operator to resize it.

## Planning Page Interaction

The Planning page should use one calendar canvas with two views rather than separate holiday and
booking pages:

1. **Consultant View** focuses the selected consultant and supports date-range selection.
2. **Team View** uses consultant rows and day columns as the approximately 20-person wallchart.
3. Public holidays are contextual calendar columns in both views, with a settings link for source and
   correction maintenance.
4. Selecting a range opens a right-hand booking drawer containing lifecycle state, generated DCC/SPA
   deductions, warnings, notes, and the final save action.

This keeps calendar selection, holiday context, and generated deductions together without forcing the
full booking form into every calendar cell. The consultant Overview remains the summary and audit
surface rather than a second leave-entry interface.
