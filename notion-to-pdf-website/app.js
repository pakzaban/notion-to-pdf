'use strict';
const form = document.querySelector('#builder');
const url = document.querySelector('#url');
const scale = document.querySelector('#scale');
const exclude = document.querySelector('#exclude');
const command = document.querySelector('#command-text');
const status = document.querySelector('#status');
// A single-quoted shell argument; supports apostrophes without executing input.
function quoteShell(value) { return "'" + value.replace(/'/g, "'\"'\"'") + "'"; }
function update() {
  document.querySelector('#percent').textContent = scale.value + '%';
  command.textContent = 'python notion_to_pdf.py ' + quoteShell(url.value.trim() || 'YOUR_NOTION_PAGE_URL') + ' -o combined.pdf' + (exclude.checked ? ' --exclude-parent' : '') + ' --scale ' + (Number(scale.value) / 100).toFixed(2);
  status.textContent = '';
}
form.addEventListener('input', update);
form.addEventListener('submit', event => event.preventDefault());
document.querySelector('#copy').addEventListener('click', async () => {
  try { await navigator.clipboard.writeText(command.textContent); status.textContent = 'Copied. Run it in your terminal.'; }
  catch { status.textContent = 'Select and copy the command above; clipboard access is unavailable.'; }
});
update();
