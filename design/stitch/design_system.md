---
name: Enterprise Blueprint
colors:
  surface: '#f8f9fb'
  surface-dim: '#d9dadc'
  surface-bright: '#f8f9fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f4f6'
  surface-container: '#edeef0'
  surface-container-high: '#e7e8ea'
  surface-container-highest: '#e1e2e4'
  on-surface: '#191c1e'
  on-surface-variant: '#434654'
  inverse-surface: '#2e3132'
  inverse-on-surface: '#f0f1f3'
  outline: '#737686'
  outline-variant: '#c3c6d7'
  surface-tint: '#0353da'
  primary: '#003da6'
  on-primary: '#ffffff'
  primary-container: '#0052d9'
  on-primary-container: '#cbd6ff'
  inverse-primary: '#b4c5ff'
  secondary: '#006c46'
  on-secondary: '#ffffff'
  secondary-container: '#84f6bc'
  on-secondary-container: '#00714a'
  tertiary: '#733500'
  on-tertiary: '#ffffff'
  tertiary-container: '#974700'
  on-tertiary-container: '#ffcdb0'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dbe1ff'
  primary-fixed-dim: '#b4c5ff'
  on-primary-fixed: '#00174b'
  on-primary-fixed-variant: '#003ea8'
  secondary-fixed: '#87f8be'
  secondary-fixed-dim: '#6adca4'
  on-secondary-fixed: '#002112'
  on-secondary-fixed-variant: '#005234'
  tertiary-fixed: '#ffdbc8'
  tertiary-fixed-dim: '#ffb689'
  on-tertiary-fixed: '#311300'
  on-tertiary-fixed-variant: '#743500'
  background: '#f8f9fb'
  on-background: '#191c1e'
  surface-variant: '#e1e2e4'
typography:
  headline-xl:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: '1.25'
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.3'
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: '1.4'
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.6'
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.5'
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: '1.4'
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: '1.3'
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  container-max: 1440px
  gutter: 1.5rem
  margin-mobile: 1rem
  margin-desktop: 2rem
  stack-sm: 0.5rem
  stack-md: 1rem
  stack-lg: 2rem
---

## Brand & Style

This design system is engineered for a high-tech enterprise B2B environment, focusing on clarity, efficiency, and professional trust. The brand personality is **authoritative yet enabling**, acting as a sophisticated "workbench" for 3D digitalization solutions. 

The visual style follows a **Corporate Modern** movement. It utilizes a structured, high-density layout that organizes complex data and AI-driven workflows into digestible, modular components. The aesthetic is defined by ample "active" white space, precise geometry, and a restrained use of color to signal importance and action. It avoids unnecessary decoration, prioritizing functional clarity and a sense of architectural stability.

## Colors

The palette is anchored by a vibrant **Enterprise Blue** (#0052D9), representing intelligence and reliability. This is the primary driver for actions and brand identity. 

- **Primary:** Used for main call-to-actions, active navigation states, and key interactive elements.
- **Supportive Accents:** Functional green and orange are utilized sparingly for status indicators and categorizing workflow stages within the canvas.
- **Neutrals:** A range of cool grays provides structure. Backgrounds remain predominantly pure white to maximize legibility, while subtle grays define container boundaries and non-interactive text.
- **Borders:** A consistent light gray (#DCDFE6) is used for "ghost" borders to separate logical sections without creating visual noise.

## Typography

The system utilizes **Inter** for its systematic and utilitarian character. It ensures high legibility across data-heavy tables and complex canvas nodes.

- **Hierarchy:** Strong weight differentiation is used to separate content. Headlines use Semibold and Bold weights with tight letter-spacing for a modern "tech" feel.
- **Body Text:** Set with generous line-height (1.5x - 1.6x) to ensure comfortable reading of long-form AI-generated reports.
- **Labels:** Small, medium-weight labels are used for metadata, timestamps, and secondary details in side panels.
- **Adaptation:** Large display headings scale down by roughly 20-30% on mobile devices to prevent excessive wrapping while maintaining visual impact.

## Layout & Spacing

This design system uses a **Fluid-Fixed Hybrid** model. While the top navigation and global container stretch to fill the viewport, the internal workspace follows a structured multi-pane layout.

- **Workspace Structure:** A three-pane architecture is preferred for the workbench: 
  1. Left sidebar (20-25%) for context/chat.
  2. Center canvas (Flexible) for the infinite blueprint.
  3. Right panel (280px-320px) for versioning and metadata.
- **Grid:** A 12-column grid is used for the landing/portal pages. 
- **Spacing Rhythm:** Based on an 8px base unit. Internal card padding is consistently 24px (1.5rem) to provide a premium, airy feel amidst dense information.

## Elevation & Depth

Visual hierarchy is achieved through **Tonal Layering** and **Subtle Ambient Shadows**. 

- **Surface Levels:** The primary background is Level 0 (White). Cards and sidebar containers sit on Level 1, defined by a 1px solid neutral border. 
- **Shadows:** We use extra-diffused, low-opacity shadows (e.g., `0 4px 20px rgba(0,0,0,0.05)`) for active elements or "floating" panels like tooltips and dropdowns.
- **Depth Cues:** The canvas uses a light gray background (#F8F9FA) to differentiate the "work surface" from the "interface chrome." Active nodes on the canvas use a slightly stronger shadow to indicate they are draggable or interactive.

## Shapes

The shape language is **Rounded**, striking a balance between approachable and professional.

- **Base Corner Radius:** 8px (0.5rem) is the standard for cards, input fields, and standard buttons.
- **Large Components:** Sections like the main dashboard containers or large hero sections may use up to 16px (1rem) for a softer, more modern framing.
- **Small Elements:** Tags, chips, and small utility buttons use a 4px or fully rounded pill-shape depending on the context of the content.

## Components

- **Buttons:** Primary buttons are solid Blue (#0052D9) with white text. Secondary buttons use a "Ghost" style (Blue border, transparent background). All have an 8px radius.
- **Cards:** White background, 1px border (#DCDFE6). Use a subtle hover state that slightly intensifies the shadow or adds a primary-colored top border.
- **Input Fields:** Large, 48px height for search/prompt bars. Use placeholder text in Gray-400 and a Blue 2px ring for the focus state.
- **Nodes/Workflow Boxes:** Within the canvas, use colored borders (Green, Blue, Orange) to signify stages. These should be 2px thick to maintain visibility at lower zoom levels.
- **Lists:** Clean, un-bulleted lists with 12px vertical spacing between items. Use icons to provide visual cues for file types (PDF, PPT, DOC).
- **Navigation:** Top-level navigation uses simple text with a bottom-indicator (Blue 3px bar) for the active state. Sidebar navigation uses a subtle background fill (#F2F3F5) for the active item.