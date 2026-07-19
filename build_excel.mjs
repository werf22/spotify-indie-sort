import fs from 'node:fs/promises';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const root = '/Users/jakub/Appky Claude/spotify-indie-sort';
const outDir = '/Users/jakub/.codex/visualizations/2026/07/14/019f6041-0ce1-79a1-9b36-3b762d0b52de';
const tracks = JSON.parse(await fs.readFile(`${root}/data/library_export.json`, 'utf8'));
const decisions = JSON.parse(await fs.readFile(`${root}/data/classification.json`, 'utf8'));
const keep = new Set(decisions.filter(x => x.decision === 'keep').map(x => x.id));
const selected = tracks.filter(t => keep.has(t.id));

const wb = Workbook.create();
const ws = wb.worksheets.add('Indie Sort');
ws.showGridLines = false;
const headers = ['#', 'Track', 'Artist(s)', 'Album', 'Spotify genres', 'Library sources', 'Spotify URL', 'Classification'];
const rows = selected.map((t, i) => [
  i + 1,
  t.name || '',
  (t.artists || []).map(a => a.name || '').join(', '),
  t.album || '',
  (t.genres || []).join(', '),
  [...new Set(t.sources || [])].join(' | '),
  `https://open.spotify.com/track/${t.id}`,
  'Strict indie-style selection',
]);
ws.getRangeByIndexes(0, 0, rows.length + 1, headers.length).values = [headers, ...rows];
ws.freezePanes.freezeRows(1);
ws.getRange('A1:H1').format = {
  fill: '#1DB954', font: { bold: true, color: '#FFFFFF' },
  horizontalAlignment: 'center', verticalAlignment: 'center',
};
ws.getRange(`A1:H${rows.length + 1}`).format.borders = { preset: 'insideHorizontal', style: 'thin', color: '#E5E7EB' };
ws.getRange(`A2:A${rows.length + 1}`).format.horizontalAlignment = 'center';
ws.getRange(`A1:A${rows.length + 1}`).format.columnWidth = 7;
ws.getRange(`B1:B${rows.length + 1}`).format.columnWidth = 34;
ws.getRange(`C1:C${rows.length + 1}`).format.columnWidth = 28;
ws.getRange(`D1:D${rows.length + 1}`).format.columnWidth = 30;
ws.getRange(`E1:E${rows.length + 1}`).format.columnWidth = 34;
ws.getRange(`F1:F${rows.length + 1}`).format.columnWidth = 34;
ws.getRange(`G1:G${rows.length + 1}`).format.columnWidth = 44;
ws.getRange(`H1:H${rows.length + 1}`).format.columnWidth = 28;
ws.getRange('A1:H1').format.rowHeight = 24;
const table = ws.tables.add(`A1:H${rows.length + 1}`, true, 'IndieSortTracks');
table.style = 'TableStyleMedium4';

await fs.mkdir(outDir, { recursive: true });
const xlsx = await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(`${outDir}/spotify_indie_sort.xlsx`);
const preview = await wb.render({ sheetName: 'Indie Sort', range: 'A1:H18', scale: 1, format: 'png' });
await fs.writeFile(`${outDir}/spotify_indie_sort_preview.png`, new Uint8Array(await preview.arrayBuffer()));
console.log(JSON.stringify({ rows: selected.length, path: `${outDir}/spotify_indie_sort.xlsx` }));
