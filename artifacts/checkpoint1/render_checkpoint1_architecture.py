"""Render the inspected architecture as one landscape page, using existing Pillow."""

from html import escape
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


OUT = Path(__file__).resolve().parent
WIDTH, HEIGHT = 1782, 1260
image = Image.new('RGB', (WIDTH, HEIGHT), '#f7f9fc')
draw = ImageDraw.Draw(image)
svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="297mm" height="210mm" '
       f'viewBox="0 0 {WIDTH} {HEIGHT}">',
       '<title>Checkpoint 1: inspected architecture and execution limits</title>',
       '<desc>One-page source-preserving external observation workflow. Existing shop '
       'services are defined but not running in the observed Ubuntu Docker inventory. '
       'Ollama is reachable; cloud configuration is disabled and unverified.</desc>',
       f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#f7f9fc"/>']


def font(size, bold=False):
    name = 'arialbd.ttf' if bold else 'arial.ttf'
    return ImageFont.truetype(str(Path('C:/Windows/Fonts') / name), size)


def text(x, y, content, size=21, colour='#182b49', bold=False):
    draw.text((x, y), content, fill=colour, font=font(size, bold))
    svg.append(f'<text x="{x}" y="{y+size}" fill="{colour}" '
               f'font-family="Arial,sans-serif" font-size="{size}" '
               f'font-weight="{"700" if bold else "400"}">{escape(content)}</text>')


def box(x, y, w, h, title, lines, colour='#e8eef7', border='#7388a4', dashed=False):
    draw.rounded_rectangle((x, y, x+w, y+h), radius=15, fill=colour, outline=border, width=2)
    dash = 'stroke-dasharray="9 6"' if dashed else ''
    svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="15" '
               f'fill="{colour}" stroke="{border}" stroke-width="2" {dash}/>')
    text(x+18, y+15, title, 24, bold=True)
    for index, line in enumerate(lines):
        text(x+18, y+57+index*29, line, 20)


def arrow(points, colour='#536b8f', dashed=False):
    draw.line(points, fill=colour, width=3)
    x, y = points[-1]
    px, py = points[-2]
    if abs(x-px) > abs(y-py):
        direction = 1 if x > px else -1
        tri = [(x, y), (x-12*direction, y-6), (x-12*direction, y+6)]
    else:
        direction = 1 if y > py else -1
        tri = [(x, y), (x-6, y-12*direction), (x+6, y-12*direction)]
    draw.polygon(tri, fill=colour)
    coords = ' '.join(f'{a},{b}' for a, b in points)
    dash = 'stroke-dasharray="9 6"' if dashed else ''
    svg.append(f'<polyline points="{coords}" fill="none" stroke="{colour}" '
               f'stroke-width="3" {dash}/><polygon points="'
               + ' '.join(f'{a},{b}' for a, b in tri) + f'" fill="{colour}"/>')


text(40, 25, 'Checkpoint 1: Eyes — inspected architecture', 37, bold=True)
text(40, 77, '23 Oct 2026 | Existing application unchanged | External observer added only under artifacts/checkpoint1', 21)
box(40, 119, 1702, 79, 'EXECUTION STATUS', [
    'Ubuntu Docker daemon available; demo inventory empty at collection. Ollama reachable. Practice drill not executed.'],
    '#fff2d9', '#c88b28')

box(40, 230, 520, 150, 'Native Docker in Ubuntu / WSL 2', [
    'Confirmed Docker Engine + Compose', 'Windows Docker Desktop pipe unavailable',
    'Observer uses: wsl -d Ubuntu -- docker'], '#e1f2e9', '#48876c')
box(40, 415, 520, 325, 'Existing shop topology (defined)', [
    'Load generator -> Envoy -> frontend',
    'Frontend -> ad, cart, recommendation,',
    'catalog, currency, checkout, shipping',
    'Checkout -> payment, cart, catalog,',
    'currency, shipping, email',
    'Shipping -> quote; cart -> Valkey',
    'Catalog -> PostgreSQL',
    'Full-only: Kafka -> accounting / fraud',
    'No application container observed running'], '#e8eef7')
box(40, 790, 520, 193, 'Existing shopping agent (unchanged)', [
    'FastAPI /prompt -> LangChain create_agent',
    'Shop tools or fixed shopping MCP tools',
    'ChatOpenAI: one LLM_BASE_URL / LLM_MODEL',
    'No log/metric/trace/history tool registry'], '#e8eef7')
box(40, 1020, 520, 170, 'Preservation / injection boundary', [
    'SHA-256 baseline: 664 existing files',
    'faultctl -> UI API -> bound flag file',
    'Not invoked: would rewrite existing config',
    'No replacement application or write tools'], '#fff2d9', '#c88b28')

box(630, 230, 500, 150, 'Existing OpenTelemetry Collector', [
    'Receives OTLP + container/host/DB metrics',
    'Observability Compose adds exporters',
    'Defined configuration; no live flow proven'], '#e8eef7')
box(630, 415, 500, 100, 'Prometheus — metrics', [
    '/api/v1/query_range; labels, times, values'])
box(630, 555, 500, 100, 'Jaeger v3 — distributed traces', [
    '/jaeger/ui/api/v3; span and trace IDs'])
box(630, 695, 500, 100, 'OpenSearch — application logs', [
    'otel-logs-*; document IDs + observed time'])
box(630, 840, 500, 143, 'Docker — health / lifecycle history', [
    'Selected state, bounded logs and events',
    'Lifecycle events != deployment history',
    'No deployment audit feed identified'], '#e1f2e9', '#48876c')
box(630, 1020, 500, 170, 'Required next integration (PROPOSED)', [
    'Running demo + compliant practice injector',
    'Fresh, evidence-backed incident observations',
    'Autonomous agent observability tools',
    'Not implemented inside the existing agent'], '#fff2d9', '#c88b28', True)

box(1200, 230, 542, 193, 'External Eyes observer (implemented)', [
    'Read-only Python / standard library',
    'Collect -> evidence IDs -> model summary',
    'Per-call UTC time, response/error, provenance',
    'No fault mutation or source import/patch'], '#e8e6fc', '#8779b5')
box(1200, 470, 542, 115, 'External model selector (implemented)', [
    'local-only / cloud-only / either-first fallback',
    'Existing shopping agent has no such router'], '#e8e6fc', '#8779b5')
box(1200, 625, 542, 143, 'Local LLM — Ollama (reachable)', [
    'http://127.0.0.1:11434/api/chat',
    'Selected installed model: qwen2.5:3b',
    'Context/output/time/CPU bounded in TOML'], '#e1f2e9', '#48876c')
box(1200, 810, 542, 143, 'Cloud LLM — disabled / unverified', [
    'Existing-compatible Chat Completions interface',
    'Operator endpoint + model + key environment',
    'No cloud connection or failover demonstrated'], '#fff2d9', '#c88b28', True)
box(1200, 1020, 542, 170, 'Outputs — artifacts/checkpoint1', [
    'Incident report + model configuration + log',
    'Per-run JSON evidence and model identity',
    'Source baseline / final hash verification',
    'One-page SVG and PNG (this sketch)'], '#e8e6fc', '#8779b5')

arrow([(560, 570), (600, 570), (600, 305), (630, 305)])
arrow([(880, 380), (880, 415)])
arrow([(855, 380), (610, 380), (610, 605), (630, 605)])
arrow([(830, 380), (585, 380), (585, 745), (630, 745)])
arrow([(1130, 465), (1160, 465), (1160, 285), (1200, 285)])
arrow([(1130, 605), (1175, 605), (1175, 320), (1200, 320)])
arrow([(1130, 745), (1190, 745), (1190, 355), (1200, 355)])
arrow([(1130, 910), (1145, 910), (1145, 390), (1200, 390)])
arrow([(1470, 423), (1470, 470)])
arrow([(1470, 585), (1470, 625)])
arrow([(1730, 585), (1760, 585), (1760, 880), (1742, 880)], dashed=True)
arrow([(1470, 768), (1180, 768), (1180, 1000), (1470, 1000), (1470, 1020)])
text(40, 1220, 'Green: confirmed reachable capability   Blue: existing definition, runtime unverified   Purple: new external artifact workflow   Amber: blocked/proposed', 19)
svg.append('</svg>')
(OUT / 'checkpoint1_architecture.svg').write_text('\n'.join(svg), encoding='utf-8')
image.save(OUT / 'checkpoint1_architecture.png')
print('Rendered one landscape page: checkpoint1_architecture.svg and .png')
