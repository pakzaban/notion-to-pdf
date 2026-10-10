# Notion pages → one PDF

Requires Python 3.10 or newer. Treat the “folder” (M1 in your screenshot) as a Notion parent page.

## Setup

Download `notion_to_pdf.py`, then run these commands in its directory:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install playwright
python -m playwright install chromium
```

Create a Notion internal integration with Read content access at https://www.notion.so/profile/integrations. In Notion, open the M1 parent page and add that integration through the page's Connections menu. Ensure it can access any contained databases, too. See the official setup guide: https://developers.notion.com/guides/get-started/quick-start.

Set your integration token locally (do not send it in chat):

```sh
export NOTION_TOKEN='your-integration-token'
```

Copy the M1 page link and run:

```sh
python notion_to_pdf.py 'https://www.notion.so/your-parent-page-id' -o M1.pdf --exclude-parent
```

Replace the sample URL with your actual link. Omit `--exclude-parent` to include M1's own content. Add `--save-html` to retain an HTML copy alongside the PDF.

## Scale and colors

PDF content is printed at 80% scale by default, on the same A4 paper size.
Use `--scale 1` for the previous size, or `--scale 0.8` explicitly.
This changes the size of the content, not a guaranteed percentage of the file size or page count.
Text colors and background highlights are preserved from Notion's named colors,
including block colors, using an approximate light-theme palette.

## Behavior and limitations

- Recursively includes child pages, even inside toggles and columns; handles paginated API results and retries rate-limit/server responses.
- Pages follow depth-first content order. Each starts on a new PDF page. Database rows follow API query order, which can differ from a saved Notion view.
- Includes database entry page bodies, but not their property tables. It does not traverse arbitrary page links, linked database views, or pages the integration cannot see.
- Text, headings, lists, checkboxes, code, tables, expanded toggles, and images are supported. Columns become a single column. This is a readable export, not an exact reproduction of Notion's layout.
- Equations are displayed as LaTeX source. Audio, video, embedded files, and attached PDFs become links; they are not embedded or merged into the output. Unsupported blocks get a visible placeholder.
- Remote images require internet access while exporting. Some attachment links expire. Saved HTML can contain these temporary asset URLs.
- A failed API call stops the export with an error. Unsupported blocks and broken images produce warnings. The script cannot detect content that Notion silently excludes from the integration's access.
- An existing output PDF is replaced. The script only reads Notion content.

API references: https://developers.notion.com/reference/get-block-children and https://developers.notion.com/reference/query-a-data-source.

Validation: CLI and offline traversal/rendering checks were run. A live Notion export requires your integration credentials and has not been tested against your workspace.
