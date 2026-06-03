# Design System Specification: PuranGPT iOS Frontend

## 1. Overview & Creative North Star
This design system is anchored by a Creative North Star we call **"Sleek iOS Vedic Scholar"**. It aims to emulate the native iOS aesthetic—specifically the look and feel of Apple Books and iOS Messages—while providing access to ancient Vedic texts.

The aesthetic is characterized by clean typography (San Francisco/Inter), subtle translucency (glassmorphism), rounded corners, and a predominantly minimalist light mode with deep contrast for dark mode. It should feel like a premium, native iOS app.

---

## 2. Colors: The Tonal Architecture
The palette utilizes standard iOS system colors.

- **Background (Light Mode)**: Pure white `#ffffff` or very light gray `#f2f2f7` for grouped lists.
- **Background (Dark Mode)**: Pure black `#000000` or very dark gray `#1c1c1e`.
- **Primary Action (Accent)**: Saffron Orange `#ff9933` (representing the Hindu/Vedic theme) or a clean iOS Blue `#007aff`.
- **Secondary Text**: `#8e8e93` (iOS Gray).
- **Surface/Card**: `#ffffff` (light) or `#2c2c2e` (dark) with subtle shadows.

### Glassmorphism & Translucency
- **Navigation Bar & Tab Bar**: Must use a frosted glass effect (`backdrop-filter: blur(20px)`) with a semi-transparent background (e.g., `rgba(255, 255, 255, 0.8)`).
- **No heavy borders**: Use ultra-thin `1px` (or `0.5px` equivalent) borders with very low opacity (`rgba(0,0,0,0.1)`) as dividers.

---

## 3. Typography: The Editorial Voice
- **Font Family**: `Inter` (as a web-safe alternative to San Francisco).
- **Large Titles**: Use heavy, large left-aligned titles for screen headers (e.g., 34pt bold).
- **Body Text**: 17pt (or 1rem) regular weight for maximum legibility, with a line-height of 1.4 to 1.5.
- **Labels**: Smaller, slightly muted text for metadata (like chapter numbers, verse numbers).

---

## 4. Components & Principles of Interaction

### Chat Interface (Scholar Screen)
- **Bubbles**: iOS Messages style. 
  - User messages: Align right, Solid Accent Color background, white text.
  - Assistant messages: Align left, light gray (`#e9e9eb`) background, black text.
- **Corners**: Highly rounded corners (e.g., `border-radius: 20px`), with the bottom-most corner (pointing to the speaker) slightly sharper.
- **Input Bar**: A pill-shaped input field at the bottom with a frosted glass container behind it.

### Cards & Lists (Home/Explore Screen)
- **Rounded Corners**: 16px to 24px corner radius for cards.
- **List Separators**: Inset dividers (starting after the icon/image) for list items.

### Provenance Badges
- **Grounded**: A subtle, pill-shaped badge with a green tint and green text.
- **Partial**: A badge with an amber/orange tint.
- **Ungrounded**: A badge with a gray tint.
These badges should appear neatly within or above the assistant's chat bubble.

---

## 5. Do's and Don'ts
### Do
- **Do** use ample whitespace and padding (standard iOS 16px or 20px margins).
- **Do** use large, bold headers that shrink upon scrolling (if applicable).
- **Do** keep the design minimalist and uncluttered.

### Don't
- **Don't** use thick borders or heavy drop shadows. Shadows should be very subtle and diffused.
- **Don't** use highly saturated colors for backgrounds. Keep backgrounds neutral and save saturation for interactive elements (buttons, toggles, badges).
