import re

def process_css():
    with open('frontend/style.css', 'r') as f:
        css = f.read()

    # Define iOS Variables
    ios_vars = """:root {
  /* Core Palette - iOS HIG Dark Mode */
  --bg-void:        #000000;
  --bg-deep:        #000000;
  --bg-panel:       #1c1c1e;
  --bg-card:        #2c2c2e;
  --bg-glass:       rgba(28, 28, 30, 0.7);
  --bg-glass-light: rgba(44, 44, 46, 0.7);
  --bg-input:       #2c2c2e;

  /* iOS Accents */
  --gold-bright:    #0a84ff; /* Kept var name to minimize breaks, but it's blue */
  --gold-main:      #0a84ff;
  --gold-dim:       #005bb5;
  --gold-ghost:     rgba(10, 132, 255, 0.15);
  --gold-glow:      rgba(10, 132, 255, 0.25);
  --saffron:        #ff375f;
  --saffron-dim:    rgba(255, 55, 95, 0.2);

  /* iOS Secondary Accents */
  --lotus-pink:     #ff375f;
  --lotus-dim:      rgba(255, 55, 95, 0.2);
  --sky-blue:       #64d2ff;
  --teal:           #30d158;

  /* Text */
  --text-primary:   #ffffff;
  --text-secondary: rgba(235, 235, 245, 0.6);
  --text-muted:     rgba(235, 235, 245, 0.3);
  --text-gold:      #0a84ff;
  --text-link:      #0a84ff;

  /* Borders & Dividers */
  --border-gold:    transparent;
  --border-subtle:  rgba(84, 84, 88, 0.65);
  --border-active:  rgba(84, 84, 88, 0.8);

  /* Shadows & Glows - Flatter for iOS */
  --shadow-card:    none;
  --shadow-gold:    none;
  --shadow-modal:   0 8px 32px rgba(0, 0, 0, 0.5);
  --glow-saffron:   none;
  --glow-gold:      none;

  /* Typography */
  --font-display:   -apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", sans-serif;
  --font-body:      -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", sans-serif;
  --font-devanagari:-apple-system, BlinkMacSystemFont, "Noto Sans Devanagari", sans-serif;
  --font-mono:      'SF Mono', 'Menlo', 'Monaco', 'Courier New', monospace;

  /* Spacing */
  --space-xs:   4px;
  --space-sm:   8px;
  --space-md:   16px;
  --space-lg:   24px;
  --space-xl:   32px;
  --space-2xl:  48px;
  --space-3xl:  64px;

  /* Radii - iOS Style */
  --radius-sm:  8px;
  --radius-md:  12px;
  --radius-lg:  16px;
  --radius-xl:  24px;
  --radius-pill:999px;

  /* Transitions */
  --t-fast:     150ms cubic-bezier(0.25, 0.1, 0.25, 1);
  --t-base:     250ms cubic-bezier(0.25, 0.1, 0.25, 1);
  --t-slow:     400ms cubic-bezier(0.25, 0.1, 0.25, 1);
  --t-spring:   500ms cubic-bezier(0.34, 1.56, 0.64, 1);

  /* Layout */
  --topbar-h:   56px;
  --sidebar-w:  260px;
}"""

    # Replace root block
    css = re.sub(r':root\s*\{[^}]+\}', ios_vars, css)

    # Remove all linear gradients using var(--gold-bright), etc.
    css = re.sub(r'background:\s*linear-gradient\([^)]+\);', 'background: var(--bg-card);', css)

    # Clean up specific buttons to be flat and iOS-like
    # .btn-primary should be iOS blue solid
    css = re.sub(r'\.btn-primary\s*\{[^}]+\}', '.btn-primary { background: var(--gold-main); color: #fff; border: none; box-shadow: none; border-radius: 12px; }', css)
    
    # Active mode button
    css = re.sub(r'\.mode-btn\.active\s*\{[^}]+\}', '.mode-btn.active { background: #2c2c2e; color: #fff; border: none; box-shadow: none; border-radius: var(--radius-pill); }', css)

    # Sidebar new chat btn
    css = re.sub(r'\.btn-new-chat\s*\{[^}]+\}', '.btn-new-chat { background: #2c2c2e; color: var(--gold-main); border: none; box-shadow: none; justify-content: flex-start; padding: 12px 16px; border-radius: 12px; font-weight: 500; }', css)
    css = re.sub(r'\.btn-new-chat:hover\s*\{[^}]+\}', '.btn-new-chat:hover { background: #3a3a3c; }', css)

    # Fix general border radius and font weights
    css = css.replace('border: 1px solid var(--border-gold);', 'border: none;')
    css = css.replace('filter: drop-shadow(0 0 8px var(--gold-glow));', 'filter: none;')
    
    # Fix chat bubbles specifically (we did this partially before, but ensuring here)
    # the user already has the iMessage styled bubbles, but we'll ensure markdown inside looks good
    
    # Let's add some markdown reset styles for iOS feel
    markdown_css = """
.message-bubble pre { background: #1c1c1e !important; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1); padding: 12px; font-size: 13px; }
.message-bubble code { font-family: var(--font-mono); color: #ff375f; }
.message-bubble pre code { color: #fff; }
.message-bubble h1, .message-bubble h2, .message-bubble h3 { font-weight: 600; letter-spacing: -0.02em; margin-top: 16px; margin-bottom: 8px; color: var(--text-primary); }
.message-bubble ul, .message-bubble ol { padding-left: 20px; margin-bottom: 12px; }
.message-bubble li { margin-bottom: 4px; }
.message.user .message-bubble code { color: #fff; background: rgba(0,0,0,0.2); }
"""
    css += markdown_css

    with open('frontend/style.css', 'w') as f:
        f.write(css)
    print("CSS overwritten with iOS HIG theme.")

if __name__ == '__main__':
    process_css()
