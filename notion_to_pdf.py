#!/usr/bin/env python3
"""Combine a Notion parent page and its descendants into a PDF. Python 3.10+."""
import argparse
import html
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


def page_id(value):
    path = urllib.parse.urlparse(value).path if '://' in value else value
    matches = re.findall(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}|[0-9a-fA-F]{32}', path)
    if not matches:
        raise ValueError('Expected a Notion page URL or page UUID.')
    return str(uuid.UUID(matches[-1]))


def esc(value):
    return html.escape(str(value), quote=True)


def link(url, label):
    if urllib.parse.urlparse(url or '').scheme not in ('http', 'https', 'mailto'):
        return label
    return f'<a href="{esc(url)}">{label}</a>'


# Notion exposes named colors, rather than exact UI RGB values. Light palette.
TEXT_COLORS = dict(gray='#787774', brown='#9F6B53', orange='#D9730D',
                   yellow='#CB912F', green='#448361', blue='#337EA9',
                   purple='#9065B0', pink='#C14C8A', red='#D44C47')
BACKGROUND_COLORS = dict(gray='#F1F1EF', brown='#F4EEEE', orange='#FBECDD',
                         yellow='#FBF3DB', green='#EDF3EC', blue='#E7F3F8',
                         purple='#F4F0F7', pink='#F9EEF3', red='#FDEBEC')


def color_style(color):
    if color.endswith('_background'):
        rgb = BACKGROUND_COLORS.get(color.removesuffix('_background'))
        return f'background-color:{rgb}' if rgb else ''
    rgb = TEXT_COLORS.get(color)
    return f'color:{rgb}' if rgb else ''


def rich(items):
    result = []
    for item in items:
        text = item.get('plain_text', item.get('text', {}).get('content', ''))
        if item.get('type') == 'equation':
            text = item['equation'].get('expression', '')
        value = esc(text)
        for key, tag in [('code', 'code'), ('bold', 'strong'), ('italic', 'em'), ('strikethrough', 's'), ('underline', 'u')]:
            if item.get('annotations', {}).get(key):
                value = f'<{tag}>{value}</{tag}>'
        style = color_style(item.get('annotations', {}).get('color', 'default'))
        if style:
            value = f'<span style="{style}">{value}</span>'
        result.append(link(item.get('href'), value))
    return ''.join(result)


class Notion:
    def __init__(self, token):
        self.token = token

    def request(self, endpoint, data=None):
        for attempt in range(6):
            request = urllib.request.Request(
                'https://api.notion.com/v1/' + endpoint,
                data=json.dumps(data).encode() if data is not None else None,
                headers={'Authorization': 'Bearer ' + self.token,
                         'Notion-Version': '2025-09-03', 'Content-Type': 'application/json'})
            time.sleep(0.35)
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    return json.load(response)
            except urllib.error.HTTPError as error:
                if (error.code == 429 or error.code >= 500) and attempt < 5:
                    time.sleep(float(error.headers.get('Retry-After', 2 ** attempt)))
                    continue
                raise RuntimeError(f'Notion API HTTP {error.code} at {endpoint.split("?")[0]}. '
                                   'Check your token and the parent page connection permissions.') from error
        raise RuntimeError('Notion API retries exhausted.')

    def paginate(self, endpoint, post=False):
        cursor = None
        while True:
            params = {'page_size': 100}
            if cursor:
                params['start_cursor'] = cursor
            response = self.request(endpoint, params) if post else self.request(endpoint + '?' + urllib.parse.urlencode(params))
            yield from response['results']
            if not response.get('has_more'):
                break
            cursor = response.get('next_cursor')
            if not cursor:
                raise RuntimeError('Notion returned has_more without a cursor.')


class Exporter:
    def __init__(self, api):
        self.api = api
        self.pages = []
        self.seen = set()
        self.warnings = set()

    def page(self, ident):
        if ident in self.seen:
            return
        self.seen.add(ident)
        meta = self.api.request('pages/' + ident)
        title = next((rich(p.get('title', [])) for p in meta.get('properties', {}).values() if p.get('type') == 'title'), '') or 'Untitled'
        print('Reading:', html.unescape(re.sub('<[^>]+>', '', title)), file=sys.stderr)
        entry = {'id': ident, 'title': title, 'body': ''}
        self.pages.append(entry)
        entry['body'] = self.blocks(ident, set())

    def blocks(self, ident, ancestors):
        if ident in ancestors:
            self.warnings.add('A cyclic synced block was omitted.')
            return '<p>[Cyclic synced block]</p>'
        ancestors = ancestors | {ident}
        result, list_type = [], None
        for block in self.api.paginate('blocks/' + ident + '/children'):
            kind = block['type']
            current_list = {'bulleted_list_item': 'ul', 'numbered_list_item': 'ol'}.get(kind)
            if current_list != list_type:
                if list_type:
                    result.append(f'</{list_type}>')
                if current_list:
                    result.append(f'<{current_list}>')
                list_type = current_list
            value = block.get(kind, {})
            text = rich(value.get('rich_text', []))
            child = ''
            if kind == 'child_page':
                self.page(block['id'])
                result.append(f'<p><a href="#{esc(block["id"])}">{esc(value.get("title", "Untitled"))}</a></p>')
                continue
            if kind == 'child_database':
                database = self.api.request('databases/' + block['id'])
                for source in database.get('data_sources', []):
                    for row in self.api.paginate('data_sources/' + source['id'] + '/query', post=True):
                        if row.get('object') == 'page':
                            self.page(row['id'])
                result.append(f'<p>Database: {esc(value.get("title", "Untitled"))} (entries included below)</p>')
                continue
            if kind == 'synced_block' and value.get('synced_from'):
                child = self.blocks(value['synced_from']['block_id'], ancestors)
            elif block.get('has_children'):
                child = self.blocks(block['id'], ancestors)
            if current_list:
                rendered = f'<li>{text}{child}</li>'
            elif kind.startswith('heading_'):
                tag = 'h' + str(min(int(kind[-1]) + 1, 6))
                rendered = f'<{tag}>{text}</{tag}>{child}'
            elif kind in ('paragraph', 'quote', 'callout', 'toggle', 'to_do'):
                tag = 'blockquote' if kind in ('quote', 'callout') else 'div'
                prefix = ('☑ ' if value.get('checked') else '☐ ') if kind == 'to_do' else ''
                rendered = f'<{tag} class="block">{prefix}{text}{child}</{tag}>'
            elif kind == 'code':
                rendered = f'<pre><code>{text}</code></pre>{child}'
            elif kind == 'equation':
                rendered = f'<pre>{esc(value.get("expression", ""))}</pre>'
                self.warnings.add('Equations are shown as LaTeX source, not typeset math.')
            elif kind == 'divider':
                rendered = '<hr>'
            elif kind == 'table':
                rendered = f'<table>{child}</table>'
            elif kind == 'table_row':
                rendered = '<tr>' + ''.join(f'<td>{rich(c)}</td>' for c in value.get('cells', [])) + '</tr>'
            elif kind == 'image':
                url = value.get(value.get('type', ''), {}).get('url', '')
                rendered = f'<figure><img src="{esc(url)}"><figcaption>{rich(value.get("caption", []))}</figcaption></figure>' if url.startswith('https://') else '<p>[Unavailable image]</p>'
            elif kind in ('bookmark', 'link_preview', 'embed', 'video', 'audio', 'file', 'pdf'):
                url = value.get('url') or value.get(value.get('type', ''), {}).get('url', '')
                rendered = '<p>' + link(url, esc(value.get('name') or kind + ': ' + url)) + '</p>'
                self.warnings.add('Attachments, video, audio, and embeds are links; attached PDFs are not merged.')
            elif kind in ('column_list', 'column', 'synced_block'):
                rendered = child
            elif kind == 'table_of_contents':
                rendered = '<p>See the combined contents at the beginning.</p>'
            else:
                rendered = f'<p>[{esc(kind)}] {text}</p>{child}'
                self.warnings.add(f'Block type {kind} is represented by a placeholder; external linked pages are not traversed.')
            style = color_style(value.get('color', 'default'))
            if style:
                rendered = re.sub(r'^<([a-z][a-z0-9]*)',
                                  lambda match: match.group(0) + f' style="{style}"',
                                  rendered, count=1)
            result.append(rendered)
        if list_type:
            result.append(f'</{list_type}>')
        return ''.join(result)

    def document(self):
        toc = ''.join(f'<li><a href="#{esc(p["id"])}">{p["title"]}</a></li>' for p in self.pages)
        body = ''.join(f'<section id="{esc(p["id"])}"><h1>{p["title"]}</h1>{p["body"]}</section>' for p in self.pages)
        return '''<!doctype html><meta charset="utf-8"><style>
        *{-webkit-print-color-adjust:exact;print-color-adjust:exact}
        body{font:11pt/1.55 Arial,sans-serif;color:#222;overflow-wrap:anywhere}
        section{break-before:page}h1,h2,h3,h4{break-after:avoid;line-height:1.25}
        a{color:inherit;text-decoration:underline}pre{white-space:pre-wrap;background:#f3f4f6;padding:12px;font-size:9pt}
        code{font-family:monospace}img{max-width:100%;max-height:230mm;object-fit:contain}
        figure{margin:14px 0}figcaption{color:#666;font-size:9pt}.block{margin:7px 0}
        blockquote{border-left:3px solid #ccc;padding-left:12px}table{border-collapse:collapse;width:100%}
        td{border:1px solid #ccc;padding:6px;vertical-align:top}tr{break-inside:avoid}
        </style><h1>Contents</h1><ol>''' + toc + '</ol>' + body


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('parent', help='Notion parent page URL or UUID')
    parser.add_argument('-o', '--output', type=Path, default=Path('combined.pdf'))
    parser.add_argument('--exclude-parent', action='store_true', help='Omit the parent page itself')
    parser.add_argument('--save-html', action='store_true', help='Also save intermediate HTML beside PDF')
    parser.add_argument('--scale', type=float, default=0.8, help='PDF content scale, 0.1 to 2.0 (default: 0.8)')
    args = parser.parse_args()
    if not 0.1 <= args.scale <= 2.0:
        parser.error('--scale must be between 0.1 and 2.0.')
    token = os.getenv('NOTION_TOKEN')
    if not token:
        parser.error('Set the NOTION_TOKEN environment variable to your integration token.')
    try:
        from playwright.sync_api import sync_playwright
        exporter = Exporter(Notion(token))
        exporter.page(page_id(args.parent))
        if args.exclude_parent:
            exporter.pages = exporter.pages[1:]
        if not exporter.pages:
            raise RuntimeError('No child pages found. Remove --exclude-parent to include the parent.')
        document = exporter.document()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if args.save_html:
            args.output.with_suffix('.html').write_text(document, encoding='utf-8')
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(java_script_enabled=False)
            page.set_content(document, wait_until='load', timeout=120000)
            broken = page.locator('img').evaluate_all('(imgs) => imgs.filter(i => !i.complete || i.naturalWidth === 0).length')
            if broken:
                exporter.warnings.add(f'{broken} image(s) failed to load.')
            page.pdf(path=str(args.output), format='A4', print_background=True, scale=args.scale,
                     margin={'top': '18mm', 'bottom': '18mm', 'left': '16mm', 'right': '16mm'})
            browser.close()
        for warning in sorted(exporter.warnings):
            print('Warning:', warning, file=sys.stderr)
        print(f'Saved {len(exporter.pages)} Notion pages to {args.output.resolve()}')
    except Exception as error:
        print(f'Export failed: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
