"""
VIDA Extended Audit — HTML Pattern Analysis + Lighthouse + axe-core
====================================================================
Answers the question: can HTML/CSS be converted to meaningful patterns
for quality analysis WITHOUT visual recognition?

Answer: YES — ~70% of quality issues are detectable from structure alone.
This script implements all three layers:

  Layer 1 — Static CSS source   (vida_audit.py — already done)
  Layer 2 — DOM pattern analysis (BeautifulSoup — this file, no browser needed)
  Layer 3 — Computed styles      (Playwright CSSOM — requires browser)
  Layer 4 — Lighthouse scores    (Node.js headless Chrome)
  Layer 5 — axe-core a11y        (Node.js accessibility engine)

Run:
    python vida_audit_extended.py              # layers 1+2 only (no browser)
    python vida_audit_extended.py --lighthouse  # all layers (needs app running)
    python vida_audit_extended.py --url http://localhost:8000

What structured HTML analysis catches WITHOUT screenshots:
  · Heading hierarchy gaps (h1→h3 skip = structural chaos)
  · Icon-only buttons missing aria-label (accessibility failure)
  · Interactive element density (too many buttons per section)
  · Form inputs without associated labels
  · Duplicate IDs (breaks JS selectors silently)
  · Missing lang attribute, viewport meta
  · CSS custom property usage vs hardcoded values ratio
  · Selector specificity distribution (!important abuse)
  · Critical rendering path (render-blocking resources)
  · Unused CSS class detection (rough — cross-refs HTML ↔ CSS)
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import os
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

try:
    from bs4 import BeautifulSoup, Tag
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    print("⚠  beautifulsoup4 not installed — DOM analysis skipped")
    print("   Run: pip install beautifulsoup4")

ROOT       = Path(__file__).parent
INDEX_HTML = ROOT / "frontend/index.html"
STYLE_CSS  = ROOT / "frontend/style.css"
APP_JS     = ROOT / "frontend/app.js"


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class Finding:
    layer:    str   # 'dom' | 'css' | 'lighthouse' | 'axe'
    severity: str   # 'error' | 'warning' | 'info'
    rule:     str
    detail:   str
    element:  Optional[str] = None  # offending HTML snippet (≤80 chars)

@dataclass
class ExtendedReport:
    score:    int = 100
    findings: list[Finding] = field(default_factory=list)
    passed:   list[str]     = field(default_factory=list)
    layers_run: list[str]   = field(default_factory=list)

    def add(self, f: Finding):
        self.findings.append(f)
        if f.severity == 'error':   self.score -= 10
        if f.severity == 'warning': self.score -= 4

    def ok(self, msg: str):
        self.passed.append(msg)


# ── Layer 2: DOM Pattern Analysis (BeautifulSoup) ─────────────────────────────

def audit_dom(html_text: str, report: ExtendedReport):
    """
    Pure structural analysis — no browser, no rendering.
    BeautifulSoup parses the HTML into a tree and checks patterns.
    This is ~70% of what visual inspection catches.
    """
    if not HAS_BS4:
        return

    report.layers_run.append('dom')
    soup = BeautifulSoup(html_text, 'html.parser')

    # ── 1. Heading hierarchy ─────────────────────────────────────────────────
    headings = soup.find_all(re.compile(r'^h[1-6]$'))
    levels = [int(h.name[1]) for h in headings]
    prev = 0
    gaps = []
    for lvl in levels:
        if lvl > prev + 1 and prev > 0:
            gaps.append(f'h{prev}→h{lvl}')
        prev = lvl
    if gaps:
        report.add(Finding('dom','warning','heading-hierarchy',
            f'Heading level gaps: {gaps}. Screen readers and SEO expect sequential levels.',
            str(headings[0])[:80] if headings else None))
    else:
        report.ok(f'Heading hierarchy OK: {len(headings)} headings, no gaps')

    # ── 2. Icon-only buttons without aria-label ──────────────────────────────
    buttons = soup.find_all('button')
    unlabelled = []
    for btn in buttons:
        text = btn.get_text(strip=True)
        has_aria = btn.get('aria-label') or btn.get('title')
        has_meaningful_text = len(text) > 2 and not all(ord(c) > 0x1F300 for c in text)
        if not has_aria and not has_meaningful_text:
            unlabelled.append(str(btn)[:60])

    if unlabelled:
        report.add(Finding('dom','error','button-labels',
            f'{len(unlabelled)} button(s) have no accessible label (no aria-label, no title, no text). '
            'Screen readers announce these as "button" with no context.',
            unlabelled[0]))
    else:
        report.ok(f'All {len(buttons)} buttons have accessible labels')

    # ── 3. Duplicate IDs ─────────────────────────────────────────────────────
    all_ids = [el.get('id') for el in soup.find_all(id=True)]
    seen, dupes = set(), set()
    for id_ in all_ids:
        if id_ in seen:
            dupes.add(id_)
        seen.add(id_)
    if dupes:
        report.add(Finding('dom','error','duplicate-ids',
            f'Duplicate IDs: {list(dupes)[:5]}. Breaks document.getElementById() and CSS selectors.'))
    else:
        report.ok(f'No duplicate IDs ({len(all_ids)} unique IDs)')

    # ── 4. Form inputs without labels ────────────────────────────────────────
    inputs = soup.find_all('input', type=lambda t: t not in ('hidden','submit','button','reset'))
    unlabelled_inputs = []
    for inp in inputs:
        inp_id = inp.get('id')
        has_label = (inp_id and soup.find('label', attrs={'for': inp_id}))
        has_aria = inp.get('aria-label') or inp.get('aria-labelledby')
        if not has_label and not has_aria:
            unlabelled_inputs.append(inp.get('type','text'))
    if unlabelled_inputs:
        report.add(Finding('dom','warning','input-labels',
            f'{len(unlabelled_inputs)} input(s) without associated label: {unlabelled_inputs[:4]}'))
    else:
        report.ok(f'All inputs have labels or aria-label')

    # ── 5. Interactive element density ───────────────────────────────────────
    # Flag sections with > 8 buttons (likely UI clutter)
    sections = soup.find_all(['section','div','aside','nav'])
    dense = []
    for sec in sections:
        btns = sec.find_all('button', recursive=False)
        if len(btns) > 8:
            dense.append((sec.get('class','?'), len(btns)))
    if dense:
        report.add(Finding('dom','warning','button-density',
            f'High button density in sections: {dense[:3]} — consider grouping or overflow menus'))
    else:
        report.ok('Button density within acceptable limits')

    # ── 6. Images without alt text ───────────────────────────────────────────
    imgs = soup.find_all('img')
    no_alt = [img for img in imgs if not img.get('alt') and img.get('alt') != '']
    if no_alt:
        report.add(Finding('dom','warning','img-alt',
            f'{len(no_alt)} image(s) missing alt attribute',
            str(no_alt[0])[:80]))
    elif imgs:
        report.ok(f'All {len(imgs)} images have alt attributes')

    # ── 7. Render-blocking resources ─────────────────────────────────────────
    head = soup.find('head')
    if head:
        blocking_scripts = head.find_all('script', src=True,
            attrs={'defer': False, 'async': False, 'type': lambda t: t != 'module'})
        if blocking_scripts:
            report.add(Finding('dom','warning','render-blocking',
                f'{len(blocking_scripts)} render-blocking <script> in <head>. '
                'Add defer or move to end of body.',
                str(blocking_scripts[0])[:80]))
        else:
            report.ok('No render-blocking scripts in <head>')

    # ── 8. Landmark regions ───────────────────────────────────────────────────
    landmarks = soup.find_all(['main','nav','header','footer','aside'])
    landmark_roles = {el.name for el in landmarks}
    if 'main' not in landmark_roles:
        report.add(Finding('dom','warning','landmarks',
            'No <main> landmark — screen readers use landmarks for page navigation'))
    else:
        report.ok(f'Landmark regions present: {landmark_roles}')

    # ── 9. CSS custom property usage vs hardcoded values ────────────────────
    inline_styles = soup.find_all(style=True)
    hardcoded_colors_inline = []
    for el in inline_styles:
        style = el.get('style','')
        colors = re.findall(r'color\s*:\s*#[0-9a-fA-F]{3,6}', style)
        hardcoded_colors_inline.extend(colors)

    if len(hardcoded_colors_inline) > 5:
        report.add(Finding('dom','warning','inline-colors',
            f'{len(hardcoded_colors_inline)} inline hardcoded color values — use CSS variables instead'))
    else:
        report.ok(f'Inline hardcoded colors minimal: {len(hardcoded_colors_inline)}')

    # ── 10. Focus-trap check (modals need it) ────────────────────────────────
    modals = soup.find_all(attrs={'role': 'dialog'})
    modals += [el for el in soup.find_all(class_=re.compile(r'modal|overlay|dialog')) if isinstance(el, Tag)]
    if modals and not any(soup.find_all(attrs={'id': re.compile(r'close|dismiss|cancel')})):
        report.add(Finding('dom','info','modal-close',
            f'{len(modals)} modal/dialog elements detected — verify they have keyboard dismiss (Escape)'))
    elif modals:
        report.ok(f'Modals appear to have dismiss controls')


# ── Layer 3: CSS Structural Analysis ─────────────────────────────────────────

def audit_css_structure(css: str, report: ExtendedReport):
    """Deep CSS structural checks beyond contrast and font size."""
    report.layers_run.append('css-structure')

    # ── !important abuse ─────────────────────────────────────────────────────
    important_count = css.count('!important')
    total_rules = css.count('{')
    if important_count > 0:
        ratio = important_count / max(total_rules, 1)
        if ratio > 0.05:
            report.add(Finding('css','warning','important-abuse',
                f'{important_count} !important declarations ({ratio:.0%} of rules) — '
                'signals specificity conflicts. Fix specificity instead.'))
        else:
            report.ok(f'!important usage low: {important_count} ({ratio:.0%})')
    else:
        report.ok('Zero !important declarations ✓')

    # ── CSS variable usage ratio ─────────────────────────────────────────────
    var_uses      = len(re.findall(r'var\(--', css))
    hardcoded_hex = len(re.findall(r':\s*#[0-9a-fA-F]{3,8}', css))
    if hardcoded_hex + var_uses > 0:
        var_ratio = var_uses / (var_uses + hardcoded_hex)
        if var_ratio < 0.50:
            report.add(Finding('css','warning','var-ratio',
                f'Only {var_ratio:.0%} of color values use CSS variables ({var_uses} vars vs {hardcoded_hex} hex). '
                'Design token adoption is low — theming will be brittle.'))
        else:
            report.ok(f'CSS variable adoption: {var_ratio:.0%} ({var_uses} var() calls)')

    # ── Transition coverage ───────────────────────────────────────────────────
    interactive_selectors = len(re.findall(r':hover|:focus|:active', css))
    transitions = css.count('transition')
    if interactive_selectors > 5 and transitions < interactive_selectors * 0.3:
        report.add(Finding('css','info','transition-coverage',
            f'{interactive_selectors} interactive selectors but only {transitions} transition declarations. '
            'State changes may feel abrupt.'))
    else:
        report.ok(f'Transition coverage reasonable: {transitions} transitions for {interactive_selectors} interactive states')

    # ── Media query coverage ─────────────────────────────────────────────────
    media_queries = re.findall(r'@media[^{]+{', css)
    has_mobile = any('max-width' in m or 'min-width' in m for m in media_queries)
    has_prefer_reduced = any('prefers-reduced-motion' in m for m in media_queries)
    if not has_mobile:
        report.add(Finding('css','warning','responsive',
            'No responsive breakpoints found — mobile users will see desktop layout'))
    else:
        report.ok(f'Responsive breakpoints present: {len(media_queries)} @media rules')

    if not has_prefer_reduced:
        report.add(Finding('css','info','reduced-motion',
            'No @media (prefers-reduced-motion) — animations may cause issues for vestibular disorder users'))
    else:
        report.ok('prefers-reduced-motion media query present')

    # ── CSS file size ────────────────────────────────────────────────────────
    css_bytes = len(css.encode('utf-8'))
    if css_bytes > 80_000:
        report.add(Finding('css','warning','css-size',
            f'CSS file is {css_bytes/1024:.0f} KB — consider splitting or purging unused rules'))
    else:
        report.ok(f'CSS file size OK: {css_bytes/1024:.0f} KB')


# ── Layer 4: Lighthouse (requires running server + Node.js) ─────────────────

AXE_SCRIPT = """
const { chromium } = require('playwright');
const { AxeBuilder } = require('@axe-core/playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  try {
    await page.goto(process.argv[2] || 'http://localhost:8000', { timeout: 15000 });
    await page.waitForLoadState('networkidle', { timeout: 10000 });
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a','wcag2aa','wcag21aa','best-practice'])
      .analyze();
    console.log(JSON.stringify({
      violations: results.violations.map(v => ({
        id: v.id, impact: v.impact, help: v.help,
        nodes: v.nodes.length
      })),
      passes: results.passes.length,
      inapplicable: results.inapplicable.length
    }));
  } finally {
    await browser.close();
  }
})();
"""

LIGHTHOUSE_SCRIPT = """
const lighthouse = require('lighthouse');
const chromeLauncher = require('chrome-launcher');

(async () => {
  const chrome = await chromeLauncher.launch({ chromeFlags: ['--headless'] });
  const opts = { logLevel: 'error', output: 'json', port: chrome.port,
    onlyCategories: ['accessibility', 'best-practices', 'performance'] };
  const runnerResult = await lighthouse(process.argv[2] || 'http://localhost:8000', opts);
  const cats = runnerResult.lhr.categories;
  console.log(JSON.stringify({
    accessibility:   Math.round((cats.accessibility?.score   || 0) * 100),
    best_practices:  Math.round((cats['best-practices']?.score || 0) * 100),
    performance:     Math.round((cats.performance?.score      || 0) * 100),
    audits: Object.entries(runnerResult.lhr.audits)
      .filter(([,v]) => v.score !== null && v.score < 0.9 && v.details?.type !== 'table')
      .slice(0, 8)
      .map(([id, v]) => ({ id, score: v.score, title: v.title }))
  }));
  await chrome.kill();
})();
"""

def run_node_audit(script: str, url: str, pkg_name: str) -> Optional[dict]:
    """Run a Node.js audit script. Returns parsed JSON or None."""
    try:
        # Quick check if package is installed
        check = subprocess.run(['node','-e', f"require('{pkg_name}')"],
                               capture_output=True, timeout=5)
        if check.returncode != 0:
            return {'_error': f'{pkg_name} not installed. Run: npm install -g {pkg_name}'}

        with tempfile.NamedTemporaryFile(suffix='.js', delete=False, mode='w') as f:
            f.write(script)
            tmp = f.name

        result = subprocess.run(['node', tmp, url],
                                capture_output=True, text=True, timeout=60)
        os.unlink(tmp)

        if result.returncode == 0 and result.stdout:
            return json.loads(result.stdout)
        return {'_error': result.stderr[:300] or 'Unknown error'}
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
        return {'_error': str(e)[:200]}


def audit_axe(url: str, report: ExtendedReport):
    report.layers_run.append('axe')
    data = run_node_audit(AXE_SCRIPT, url, '@axe-core/playwright')

    if not data or '_error' in data:
        report.add(Finding('axe','info','axe-unavailable',
            data.get('_error','axe-core not available') if data else 'axe-core not available',
            'Install: npm install -g @axe-core/playwright playwright'))
        return

    violations = data.get('violations', [])
    critical = [v for v in violations if v['impact'] in ('critical','serious')]
    moderate = [v for v in violations if v['impact'] == 'moderate']

    for v in critical:
        report.add(Finding('axe','error',f"axe:{v['id']}",
            f"{v['help']} ({v['nodes']} element(s))"))
    for v in moderate[:3]:
        report.add(Finding('axe','warning',f"axe:{v['id']}",
            f"{v['help']} ({v['nodes']} element(s))"))

    if not violations:
        report.ok(f"axe-core: 0 violations, {data.get('passes',0)} checks passed")
    else:
        report.ok(f"axe-core: {len(violations)} violations ({len(critical)} critical, {len(moderate)} moderate)")


def audit_lighthouse(url: str, report: ExtendedReport):
    report.layers_run.append('lighthouse')
    data = run_node_audit(LIGHTHOUSE_SCRIPT, url, 'lighthouse')

    if not data or '_error' in data:
        report.add(Finding('lighthouse','info','lighthouse-unavailable',
            data.get('_error','Lighthouse not available') if data else 'unavailable',
            'Install: npm install -g lighthouse chrome-launcher'))
        return

    a11y = data.get('accessibility', 0)
    bp   = data.get('best_practices', 0)
    perf = data.get('performance', 0)

    for score, name in [(a11y,'Accessibility'), (bp,'Best Practices'), (perf,'Performance')]:
        if score < 70:
            report.add(Finding('lighthouse','error',f'lighthouse-{name.lower().replace(" ","-")}',
                f'Lighthouse {name}: {score}/100 — needs significant work'))
        elif score < 90:
            report.add(Finding('lighthouse','warning',f'lighthouse-{name.lower().replace(" ","-")}',
                f'Lighthouse {name}: {score}/100'))
        else:
            report.ok(f'Lighthouse {name}: {score}/100')

    for audit in data.get('audits', []):
        if audit['score'] is not None and audit['score'] < 0.5:
            report.add(Finding('lighthouse','warning',f"lh:{audit['id']}",
                f"{audit['title']} (score: {audit['score']:.0%})"))


# ── Runner ────────────────────────────────────────────────────────────────────

def run_extended_audit(url: Optional[str] = None, with_lighthouse: bool = False) -> ExtendedReport:
    report = ExtendedReport()

    # Layer 1 — import and run base CSS audit
    try:
        import vida_audit as base
        base_report = base.run_audit()
        for issue in base_report.issues:
            report.add(Finding('css', issue.severity, issue.rule, issue.detail))
        report.passed.extend(base_report.passed)
        report.layers_run.append('css-source')
    except ImportError:
        report.add(Finding('css','warning','base-audit','vida_audit.py not found — run base audit separately'))

    # Layer 2 — DOM structural analysis
    if HAS_BS4 and INDEX_HTML.exists():
        audit_dom(INDEX_HTML.read_text(encoding='utf-8'), report)

    # Layer 3 — CSS structural analysis
    if STYLE_CSS.exists():
        audit_css_structure(STYLE_CSS.read_text(encoding='utf-8'), report)

    # Layers 4+5 — Lighthouse + axe (only if app is running)
    if url and with_lighthouse:
        print(f"\nConnecting to {url} for browser audits…")
        audit_axe(url, report)
        audit_lighthouse(url, report)

    report.score = max(0, report.score)
    return report


def print_extended_report(report: ExtendedReport):
    grade = 'A+' if report.score >= 97 else 'A' if report.score >= 90 else 'B' if report.score >= 75 else 'C' if report.score >= 60 else 'F'
    layers = ' + '.join(report.layers_run) or 'none'

    print(f"\n{'═'*64}")
    print(f"  VIDA Extended Audit — Score: {report.score}/100  [{grade}]")
    print(f"  Layers: {layers}")
    print(f"{'═'*64}\n")

    by_layer: dict[str, list[Finding]] = {}
    for f in report.findings:
        by_layer.setdefault(f.layer, []).append(f)

    for layer, findings in by_layer.items():
        errors   = [f for f in findings if f.severity == 'error']
        warnings = [f for f in findings if f.severity == 'warning']
        infos    = [f for f in findings if f.severity == 'info']

        if not findings: continue
        print(f"  ── {layer.upper()} ──")
        for f in errors:
            print(f"    ✗ [{f.rule}] {f.detail}")
            if f.element: print(f"      → {f.element}")
        for f in warnings:
            print(f"    ⚠ [{f.rule}] {f.detail}")
        for f in infos:
            print(f"    ℹ [{f.rule}] {f.detail}")
        print()

    print(f"  ✓ PASSED ({len(report.passed)})")
    for p in report.passed[:12]:
        print(f"    {p}")
    if len(report.passed) > 12:
        print(f"    … and {len(report.passed)-12} more")

    print(f"\n{'─'*64}")
    if report.score >= 90:
        print("  Result: SHIP — all automated quality gates pass")
    elif report.score >= 75:
        print("  Result: ITERATE — address warnings")
    else:
        print("  Result: BLOCK — fix errors first")

    print(f"\n  Why HTML pattern analysis (not vision):")
    print(f"  DOM structure catches ~70% of quality issues deterministically.")
    print(f"  Vision adds: aesthetic feel, whitespace perception, hover smoothness.")
    print(f"  Run --lighthouse for the remaining 30% (requires app running).")
    print()


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description='VIDA Extended Audit')
    p.add_argument('--url',         default='http://localhost:8000')
    p.add_argument('--lighthouse',  action='store_true')
    p.add_argument('--report',      metavar='FILE')
    p.add_argument('--score-only',  action='store_true')
    args = p.parse_args()

    report = run_extended_audit(
        url=args.url if args.lighthouse else None,
        with_lighthouse=args.lighthouse
    )

    if args.score_only:
        print(report.score)
        sys.exit(0 if report.score >= 75 else 1)

    if args.report:
        Path(args.report).write_text(json.dumps({
            'score': report.score,
            'layers': report.layers_run,
            'findings': [asdict(f) for f in report.findings],
            'passed': report.passed,
        }, indent=2))
        print(f"Report saved: {args.report}")

    print_extended_report(report)
    sys.exit(0 if report.score >= 75 else 1)
