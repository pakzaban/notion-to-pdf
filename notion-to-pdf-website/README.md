# Notion → PDF

A Python tool and static project website by pakzaban. Combine a Notion parent page and its descendants into one PDF, with adjustable scale and text colors.

See [USAGE.md](USAGE.md) for installation, integration setup, and limitations. The website's command builder runs locally in the browser. Conversion runs on your computer using Python and Playwright.

## Publish with GitHub Pages

1. Create a public GitHub repository named `notion-to-pdf` under `pakzaban`.
2. Upload this folder's contents to the repository root (including `index.html`, `style.css`, `app.js`, `notion_to_pdf.py`, and `USAGE.md`). Do not upload tokens or exported private notes.
3. In **Settings → Pages**, select **Deploy from a branch**, choose **main** and **/ (root)**, then save.
4. Once GitHub finishes deployment, the expected website address is `https://pakzaban.github.io/notion-to-pdf/`.

This address is a deployment target, not confirmation that the site is live.

GitHub's instructions: https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site

No build step or server is needed for the website. To preview locally: `python3 -m http.server 8000`, then visit `http://localhost:8000`.
