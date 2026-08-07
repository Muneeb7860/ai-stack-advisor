const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  Header, Footer, PageNumber, NumberFormat, LevelFormat, convertInchesToTwip,
  TableOfContents, PageBreak, VerticalAlign, ImageRun
} = require('docx');

const NAVY = '1F3B57';
const ACCENT = '2E5C8A';
const LIGHT = 'EAF0F6';
const MUTED = '5B6B7C';
const GOOD = '2E7D4F';
const WARN = 'A85D00';

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 360, after: 160 },
    border: { bottom: { color: NAVY, space: 4, style: BorderStyle.SINGLE, size: 6 } },
    children: [new TextRun({ text, bold: true, color: NAVY, size: 30 })],
  });
}
function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 280, after: 120 },
    children: [new TextRun({ text, bold: true, color: ACCENT, size: 24 })],
  });
}
function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    spacing: { before: 200, after: 100 },
    children: [new TextRun({ text, bold: true, color: '333333', size: 21 })],
  });
}
function p(text, opts = {}) {
  return new Paragraph({
    spacing: { after: 160, line: 276 },
    children: [new TextRun({ text, size: 21, ...opts })],
  });
}
function pRuns(runs, opts = {}) {
  return new Paragraph({ spacing: { after: 160, line: 276 }, ...opts, children: runs });
}
function bullet(text, level = 0) {
  return new Paragraph({
    numbering: { reference: 'bullet-list', level },
    spacing: { after: 90, line: 264 },
    children: [new TextRun({ text, size: 21 })],
  });
}
function bulletBold(boldText, rest, level = 0) {
  return new Paragraph({
    numbering: { reference: 'bullet-list', level },
    spacing: { after: 90, line: 264 },
    children: [
      new TextRun({ text: boldText, bold: true, size: 21 }),
      new TextRun({ text: rest, size: 21 }),
    ],
  });
}
function numbered(text, level = 0, ref = 'numbered-list') {
  // ref lets independent numbered lists in the same document restart at 1 — Word/docx-js
  // continues the counter for every paragraph sharing the same numbering "reference", so two
  // unrelated numbered lists using the default reference render as one continuous sequence
  // (e.g. list A items 1-5 followed by list B rendering as 6-9 instead of 1-4).
  return new Paragraph({
    numbering: { reference: ref, level },
    spacing: { after: 90, line: 264 },
    children: [new TextRun({ text, size: 21 })],
  });
}
function cell(text, opts = {}) {
  const { bold = false, shade = null, width = null, color = '000000', align = AlignmentType.LEFT, size = 19 } = opts;
  return new TableCell({
    width: width ? { size: width, type: WidthType.DXA } : undefined,
    shading: shade ? { type: ShadingType.CLEAR, fill: shade } : undefined,
    verticalAlign: VerticalAlign.CENTER,
    margins: { top: 80, bottom: 80, left: 100, right: 100 },
    children: [new Paragraph({
      alignment: align,
      children: [new TextRun({ text, bold, size, color })],
    })],
  });
}
function multiCell(paragraphs, opts = {}) {
  const { shade = null, width = null } = opts;
  return new TableCell({
    width: width ? { size: width, type: WidthType.DXA } : undefined,
    shading: shade ? { type: ShadingType.CLEAR, fill: shade } : undefined,
    margins: { top: 80, bottom: 80, left: 100, right: 100 },
    children: paragraphs,
  });
}
function reqTable(headerLabels, colWidths, rows) {
  const total = colWidths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: colWidths,
    rows: [
      new TableRow({
        tableHeader: true,
        children: headerLabels.map((label, i) => cell(label, { bold: true, shade: NAVY, color: 'FFFFFF', width: colWidths[i], size: 18 })),
      }),
      ...rows.map((r, idx) => new TableRow({
        children: r.map((val, i) => typeof val === 'object' && val.paragraphs
          ? multiCell(val.paragraphs, { width: colWidths[i], shade: idx % 2 ? LIGHT : null })
          : cell(String(val), { width: colWidths[i], shade: idx % 2 ? LIGHT : null })),
      })),
    ],
  });
}
function pageBreak() {
  return new Paragraph({ children: [new PageBreak()] });
}
function hr() {
  return new Paragraph({
    spacing: { before: 100, after: 200 },
    border: { bottom: { color: 'CCCCCC', space: 1, style: BorderStyle.SINGLE, size: 4 } },
    children: [],
  });
}
function coverTitle(title, subtitle, meta) {
  return [
    new Paragraph({ spacing: { before: 2400, after: 200 }, alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: 'AI STACK ADVISOR', bold: true, size: 22, color: MUTED, characterSpacing: 20 })] }),
    new Paragraph({ spacing: { after: 200 }, alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: title, bold: true, size: 56, color: NAVY })] }),
    new Paragraph({ spacing: { after: 800 }, alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: subtitle, size: 26, color: ACCENT, italics: true })] }),
    ...meta.map(([k, v]) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 },
      children: [new TextRun({ text: `${k}:  `, bold: true, size: 20, color: MUTED }), new TextRun({ text: v, size: 20, color: '333333' })] })),
    pageBreak(),
  ];
}

const numberingConfig = {
  config: [
    {
      reference: 'bullet-list',
      levels: [
        { level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 260 } } } },
        { level: 1, format: LevelFormat.BULLET, text: '–', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 260 } } } },
      ],
    },
    {
      reference: 'numbered-list',
      levels: [
        { level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 260 } } } },
      ],
    },
    // Extra independent numbered-list references so a document can have more than one
    // numbered list without the counter continuing across them (see numbered() above).
    {
      reference: 'numbered-list-2',
      levels: [
        { level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 260 } } } },
      ],
    },
    {
      reference: 'numbered-list-3',
      levels: [
        { level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 260 } } } },
      ],
    },
  ],
};

function baseDoc({ sections }) {
  return new Document({
    numbering: numberingConfig,
    styles: {
      default: { document: { run: { font: 'Calibri', size: 21 } } },
    },
    sections,
  });
}

function standardPage(children, docTitle) {
  return {
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1080, bottom: 1080, left: 1260, right: 1260 },
      },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          border: { bottom: { color: 'CCCCCC', space: 4, style: BorderStyle.SINGLE, size: 4 } },
          tabStops: [{ type: 'right', position: convertInchesToTwip(6.7) }],
          children: [
            new TextRun({ text: docTitle, size: 16, color: MUTED }),
            new TextRun({ text: '\tAI Stack Advisor', size: 16, color: MUTED }),
          ],
        })],
      }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [
            new TextRun({ text: 'Page ', size: 16, color: MUTED }),
            new TextRun({ children: [PageNumber.CURRENT], size: 16, color: MUTED }),
            new TextRun({ text: ' of ', size: 16, color: MUTED }),
            new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 16, color: MUTED }),
          ],
        })],
      }),
    },
    children,
  };
}

module.exports = {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle, TableOfContents, ImageRun,
  NAVY, ACCENT, LIGHT, MUTED, GOOD, WARN,
  h1, h2, h3, p, pRuns, bullet, bulletBold, numbered, cell, multiCell, reqTable,
  pageBreak, hr, coverTitle, baseDoc, standardPage,
};
