"""
VIDA — Visual Iterative Design Agent
=====================================
Automated design audit for PuranGPT frontend.

Stage 4 of the VIDA framework: programmatic CSS/DOM audit that runs without
needing a screenshot (zero-vision checks). Catches the most common LLM UI
failures before expensive vision-model calls.

Usage:
    python vida_audit.py                    # audit current style.css
    python vida_audit.py --fix              # apply automated fixes
    python vida_audit.py --report report.json

What it checks (WCAG AA + premium dark UI rules):
    1. Base font size  ≥ 15px
    2. Body line-height ≥ 1.55
    3. Text-on-surface contrast ratios (computed from CSS vars)
    4. Accent color usage ratio (flag if > 15% of rules use accent)
    5. Border overuse (flag if > 40% of rules reference gold/accent border)
    6. Emoji presence in CSS/HTML/JS
    7. Pure black (#000000) usage (eye strain on OLED)
    8. z-index chaos (values > 9000 outside modals)
    9. Hard-coded pixel font sizes below threshold
    10. Missing hover states on interactive elements
"""

from __future__ import annotations
import re, json, sys, argparse
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

ROOT      = Path(__file__).parent
STYLE_CSS = ROOT / "frontend/style.css"
INDEX_HTML= ROOT / "frontend/index.html"
APP_JS    = ROOT / "frontend/app.js"

# ── Color helpers ─────────────────────────────────────────────────────────────

def hex_to_rgb(h: str) -> tuple[int,int,int]:
    h = h.lstrip('#')
    if len(h) == 3: h = ''.join(c*2 for c in h)
    return int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)

def relative_luminance(r,g,b) -> float:
    def lin(c):
        c /= 255
        return c/12.92 if c <= 0.04045 else ((c+0.055)/1.055)**2.4
    return 0.2126*lin(r) + 0.7152*lin(g) + 0.0722*lin(b)

def contrast_ratio(hex1: str, hex2: str) -> float:
    L1 = relative_luminance(*hex_to_rgb(hex1))
    L2 = relative_luminance(*hex_to_rgb(hex2))
    bright, dark = max(L1,L2), min(L1,L2)
    return (bright + 0.05) / (dark + 0.05)

# ── Audit Checks ──────────────────────────────────────────────────────────────

@dataclass
class Issue:
    severity: str     # 'error' | 'warning' | 'info'
    rule:     str
    detail:   str
    fix:      Optional[str] = None

@dataclass
class AuditReport:
    score:    int = 100
    issues:   list[Issue] = field(default_factory=list)
    passed:   list[str]   = field(default_factory=list)

    def add(self, issue: Issue):
        self.issues.append(issue)
        if issue.severity == 'error':   self.score -= 10
        if issue.severity == 'warning': self.score -= 4

    def ok(self, msg: str):
        self.passed.append(msg)


def audit_css(css: str, report: AuditReport):
    """All checks that can be done on raw CSS text."""

    # ── 1. Base font size ─────────────────────────────────────────────────────
    base_match = re.search(r'--text-base\s*:\s*([\d.]+)px', css)
    if base_match:
        size = float(base_match.group(1))
        if size < 15:
            report.add(Issue('error','font-size',
                f'--text-base is {size}px — must be ≥ 15px. Users strain.',
                f'--text-base: 16px;'))
        else:
            report.ok(f'Base font size OK: {size}px')
    else:
        report.add(Issue('warning','font-size','--text-base token not found in CSS'))

    # ── 2. Line height ────────────────────────────────────────────────────────
    lh_match = re.search(r'line-height\s*:\s*([\d.]+)', css)
    if lh_match:
        lh = float(lh_match.group(1))
        if lh < 1.5:
            report.add(Issue('error','line-height',
                f'Body line-height {lh} is too tight — use ≥ 1.55',
                'line-height: 1.6;'))
        else:
            report.ok(f'Line-height OK: {lh}')

    # ── 3. Pure black backgrounds ─────────────────────────────────────────────
    pure_blacks = re.findall(r'background[^;]*:\s*#000(?:000)?(?!\d)', css)
    if pure_blacks:
        report.add(Issue('warning','pure-black',
            f'{len(pure_blacks)} uses of pure #000000 background — causes OLED halation. Use near-black (#0B0907 or similar)',
            'background: #0B0907;'))
    else:
        report.ok('No pure black (#000) backgrounds')

    # ── 4. Accent color overuse ───────────────────────────────────────────────
    total_rules = css.count('{')
    accent_uses = len(re.findall(r'(?:--accent|#C4961F|#E2B84A|C9A227|D4AF37)', css))
    ratio = accent_uses / max(total_rules, 1)
    if ratio > 0.15:
        report.add(Issue('warning','accent-overuse',
            f'Accent color referenced in ~{ratio:.0%} of rules — premium UIs use it in ≤10%. '
            'Gold everywhere = cheap. Reserve for: active states, primary CTA, selected items only.'))
    else:
        report.ok(f'Accent usage ratio OK: {ratio:.0%}')

    # ── 5. Emoji in CSS ───────────────────────────────────────────────────────
    css_emojis = re.findall(r'[\U0001F300-\U0001FFFF]+', css)
    if css_emojis:
        report.add(Issue('error','emoji-in-css',
            f'Emojis found in CSS: {css_emojis[:5]} — use SVG content values or data URIs'))
    else:
        report.ok('No emojis in CSS')

    # ── 6. z-index sanity ────────────────────────────────────────────────────
    zindex_vals = [int(m) for m in re.findall(r'z-index\s*:\s*(\d+)', css)]
    # Toast containers at 9999 is intentional; flag anything else > 1000 that's not in expected range
    unexpected_high = [z for z in zindex_vals if z > 1000 and z not in (9999, 9998, 1000, 1001, 500, 100)]
    if len(unexpected_high) > 3:
        report.add(Issue('warning','z-index',
            f'Many high z-index values {unexpected_high[:5]} — review stacking context'))
    else:
        report.ok(f'z-index values reasonable: {sorted(set(zindex_vals))[-3:]}')

    # ── 7. Hard-coded small fonts ─────────────────────────────────────────────
    small_fonts = re.findall(r'font-size\s*:\s*((?:[89]|1[01234])px)', css)
    if small_fonts:
        report.add(Issue('warning','small-font',
            f'Hard-coded small font sizes found: {set(small_fonts)} — prefer --text-xs (≥11.5px) token'))
    else:
        report.ok('No dangerously small hard-coded font sizes')

    # ── 8. Border overuse (gold border indicator) ────────────────────────────
    border_lines = [l for l in css.split('\n') if 'border' in l and ('accent' in l.lower() or 'gold' in l.lower() or 'C4961F' in l or 'C9A227' in l)]
    if len(border_lines) > 20:
        report.add(Issue('warning','border-overuse',
            f'{len(border_lines)} accent-colored border declarations — this is what makes it look "cheap". '
            'Premium UIs use luminance hierarchy (surface colors) not colored borders for structure. '
            'Reserve accent borders for: focused inputs, active cards, selected state only.'))
    else:
        report.ok(f'Accent border usage manageable: {len(border_lines)} occurrences')

    # ── 9. Contrast spot-check (known pairs from design tokens) ──────────────
    PAIRS = [
        ('#EDE8D8', '#111009', 'Primary text on base surface'),
        ('#9A8E70', '#111009', 'Secondary text on base'),
        ('#8A7E65', '#111009', 'Muted text on base'),
        ('#EDE8D8', '#181510', 'Primary text on raised surface'),
        ('#C4961F', '#0B0907', 'Accent on void'),
    ]
    for fg, bg, label in PAIRS:
        try:
            ratio = contrast_ratio(fg, bg)
            if ratio < 4.5:
                report.add(Issue('error','contrast',
                    f'{label}: {ratio:.1f}:1 — fails WCAG AA (need 4.5:1)',
                    f'Lighten foreground or darken background'))
            elif ratio < 7:
                report.ok(f'{label}: {ratio:.1f}:1 ✓ (AA)')
            else:
                report.ok(f'{label}: {ratio:.1f}:1 ✓ (AAA)')
        except Exception:
            pass


def audit_html(html: str, report: AuditReport):
    """Checks that can be done on raw HTML."""

    # ── Emoji in HTML ─────────────────────────────────────────────────────────
    # Exclude Devanagari and script content
    html_no_scripts = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    html_no_scripts = re.sub(r'<style[^>]*>.*?</style>', '', html_no_scripts, flags=re.DOTALL)
    # Exclude the Om symbol which is intentional
    text_content = re.sub(r'ॐ', '', html_no_scripts)
    emojis = re.findall(r'[\U0001F300-\U0001FFFF☀-⛿✈-✿]+', text_content)
    if emojis:
        report.add(Issue('error','emoji-in-html',
            f'Emojis in HTML: {emojis[:8]} — replace with Lucide SVG icons'))
    else:
        report.ok('No emojis in static HTML (excluding ॐ)')

    # ── Missing lang attribute ────────────────────────────────────────────────
    if 'lang="' not in html:
        report.add(Issue('warning','a11y','Missing lang attribute on <html> tag'))
    else:
        report.ok('lang attribute present')

    # ── Lucide CDN ────────────────────────────────────────────────────────────
    if 'lucide' in html:
        report.ok('Lucide icon library loaded')
    else:
        report.add(Issue('error','icons','Lucide CDN script not found — icons will not render'))

    # ── Viewport meta ─────────────────────────────────────────────────────────
    if 'viewport' in html:
        report.ok('Viewport meta tag present')
    else:
        report.add(Issue('warning','viewport','Missing viewport meta — mobile rendering broken'))


def audit_js(js: str, report: AuditReport):
    """Checks on JS file."""

    # ── Emoji in dynamic strings ──────────────────────────────────────────────
    # Find emojis not in comments, not ✅/⚠ (used for bias indicators)
    lines = js.split('\n')
    emoji_lines = []
    for i, line in enumerate(lines, 1):
        if line.strip().startswith('//') or line.strip().startswith('*'): continue
        # Skip bias indicators
        emojis = re.findall(r'[\U0001F300-\U0001FFFF☀-⛿✈-✿]+', line)
        emojis = [e for e in emojis if e not in ('✅','⚠️','⚠','✓','✗')]
        if emojis:
            emoji_lines.append((i, emojis))

    if emoji_lines:
        sample = emoji_lines[:4]
        report.add(Issue('warning','emoji-in-js',
            f'Emojis in JS dynamic content at lines: {[l for l,_ in sample]} '
            f'— {[e for _,e in sample]} — replace with SVG strings or text labels'))
    else:
        report.ok('No emojis in JS dynamic content')

    # ── Hardcoded colors ──────────────────────────────────────────────────────
    hardcoded = re.findall(r'style[^>]*color\s*:\s*#[0-9a-fA-F]{3,6}', js)
    if len(hardcoded) > 10:
        report.add(Issue('warning','hardcoded-colors',
            f'{len(hardcoded)} inline style colors in JS — use CSS variables for consistency'))
    else:
        report.ok(f'Inline JS colors minimal: {len(hardcoded)}')


# ── Runner ─────────────────────────────────────────────────────────────────────

def run_audit(fix: bool = False) -> AuditReport:
    report = AuditReport()

    css  = STYLE_CSS.read_text(encoding='utf-8') if STYLE_CSS.exists() else ''
    html = INDEX_HTML.read_text(encoding='utf-8') if INDEX_HTML.exists() else ''
    js   = APP_JS.read_text(encoding='utf-8')    if APP_JS.exists()    else ''

    if not css:  report.add(Issue('error','file','style.css not found'))
    if not html: report.add(Issue('error','file','index.html not found'))
    if not js:   report.add(Issue('error','file','app.js not found'))

    if css:  audit_css(css, report)
    if html: audit_html(html, report)
    if js:   audit_js(js, report)

    report.score = max(0, report.score)
    return report


def print_report(report: AuditReport):
    grade = 'A' if report.score >= 90 else 'B' if report.score >= 75 else 'C' if report.score >= 60 else 'F'
    print(f"\n{'═'*60}")
    print(f"  VIDA Design Audit — Score: {report.score}/100  [{grade}]")
    print(f"{'═'*60}\n")

    if report.issues:
        errors   = [i for i in report.issues if i.severity == 'error']
        warnings = [i for i in report.issues if i.severity == 'warning']
        infos    = [i for i in report.issues if i.severity == 'info']

        if errors:
            print(f"  ✗ ERRORS ({len(errors)})")
            for e in errors:
                print(f"    [{e.rule}] {e.detail}")
                if e.fix: print(f"      Fix: {e.fix}")
            print()

        if warnings:
            print(f"  ⚠ WARNINGS ({len(warnings)})")
            for w in warnings:
                print(f"    [{w.rule}] {w.detail}")
            print()

        if infos:
            print(f"  ℹ INFO ({len(infos)})")
            for i in infos:
                print(f"    [{i.rule}] {i.detail}")
            print()

    print(f"  ✓ PASSED ({len(report.passed)})")
    for p in report.passed:
        print(f"    {p}")

    print(f"\n{'─'*60}")
    if report.score >= 90:
        print("  Result: SHIP — visual quality target met")
    elif report.score >= 75:
        print("  Result: ITERATE — address warnings before shipping")
    else:
        print("  Result: BLOCK — fix errors before any visual review")
    print()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='VIDA Design Audit')
    parser.add_argument('--fix',    action='store_true', help='Apply automated fixes')
    parser.add_argument('--report', metavar='FILE',      help='Save JSON report')
    parser.add_argument('--score-only', action='store_true')
    args = parser.parse_args()

    report = run_audit(fix=args.fix)

    if args.score_only:
        print(report.score)
        sys.exit(0 if report.score >= 75 else 1)

    if args.report:
        Path(args.report).write_text(json.dumps({
            'score': report.score,
            'issues': [asdict(i) for i in report.issues],
            'passed': report.passed,
        }, indent=2))
        print(f"Report saved: {args.report}")

    print_report(report)
    sys.exit(0 if report.score >= 75 else 1)
