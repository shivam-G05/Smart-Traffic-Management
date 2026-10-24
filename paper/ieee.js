// Shared helpers for building IEEE-conference-style Word documents with
// docx-js: US Letter, 10 pt Times New Roman, two 3.5" columns, small-caps
// section headings, IEEE table and figure captions.

const fs = require("fs");
const path = require("path");
const {
  AlignmentType, BorderStyle, ImageRun, LevelFormat, Paragraph, SectionType, Table, TableCell, TableRow,
  TabStopType, TextRun, VerticalAlign, WidthType,
} = require("docx");

const FONT = "Times New Roman";
const PAGE = { size: { width: 12240, height: 15840 }, margin: { top: 1080, bottom: 1440, left: 900, right: 900 } };
const COL_GAP = 360; // 0.25"
const COL_WIDTH = (12240 - 900 - 900 - COL_GAP) / 2; // 5040 DXA = 3.5"

// Inline markup: *italic*, **bold**, _{sub}, ^{sup}. Enough for symbols
// like *t*_{g} or *D*_{A} without a full equation editor.
function runs(text, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*|_\{[^}]+\}|\^\{[^}]+\})/g;
  let last = 0;
  for (const m of text.matchAll(re)) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), font: FONT, ...base }));
    const tok = m[0];
    if (tok.startsWith("**")) out.push(new TextRun({ text: tok.slice(2, -2), font: FONT, ...base, bold: true }));
    else if (tok.startsWith("*")) out.push(new TextRun({ text: tok.slice(1, -1), font: FONT, ...base, italics: true }));
    else if (tok.startsWith("_{")) out.push(new TextRun({ text: tok.slice(2, -1), font: FONT, ...base, subScript: true }));
    else out.push(new TextRun({ text: tok.slice(2, -1), font: FONT, ...base, superScript: true }));
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), font: FONT, ...base }));
  return out;
}

const SIZE = { body: 20, small: 16, abstract: 18, title: 48, author: 20, affil: 18 };

function para(text, opts = {}) {
  return new Paragraph({
    alignment: opts.align ?? AlignmentType.JUSTIFIED,
    indent: opts.noIndent ? undefined : { firstLine: 204 },
    spacing: { after: opts.after ?? 0, before: opts.before ?? 0, line: 240 },
    keepNext: opts.keepNext,
    children: runs(text, { size: opts.size ?? SIZE.body }),
  });
}

// "Lead: text" paragraph with an italic run-in head, as IEEE uses for
// paragraph-level headings.
function runIn(head, text) {
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    indent: { firstLine: 204 },
    spacing: { line: 240 },
    children: [new TextRun({ text: `${head}: `, font: FONT, size: SIZE.body, italics: true }),
      ...runs(text, { size: SIZE.body })],
  });
}

function bullet(text, ref = "bullets") {
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    numbering: { reference: ref, level: 0 },
    spacing: { line: 240 },
    children: runs(text, { size: SIZE.body }),
  });
}

const ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"];
let sectionNo = 0;
let subNo = 0;

function heading(text) {
  const label = `${ROMAN[sectionNo++]}. `;
  subNo = 0;
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 160, after: 80 },
    keepNext: true,
    children: [new TextRun({ text: label + text, font: FONT, size: SIZE.body, smallCaps: true })],
  });
}

function unnumberedHeading(text) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 160, after: 80 },
    keepNext: true,
    children: [new TextRun({ text, font: FONT, size: SIZE.body, smallCaps: true })],
  });
}

function subheading(text) {
  const label = `${String.fromCharCode(65 + subNo++)}. `;
  return new Paragraph({
    spacing: { before: 80, after: 40 },
    keepNext: true,
    children: [new TextRun({ text: label + text, font: FONT, size: SIZE.body, italics: true })],
  });
}

// Centered equation with its number flush right.
function equation(text, number) {
  return new Paragraph({
    tabStops: [{ type: TabStopType.CENTER, position: COL_WIDTH / 2 }, { type: TabStopType.RIGHT, position: COL_WIDTH }],
    spacing: { before: 60, after: 60 },
    children: [new TextRun({ text: "\t", font: FONT }), ...runs(text, { size: SIZE.body }),
      new TextRun({ text: `\t(${number})`, font: FONT, size: SIZE.body })],
  });
}

function figure(file, widthIn, caption, number) {
  const buf = fs.readFileSync(file);
  const { width, height } = pngSize(buf);
  const w = Math.round(widthIn * 96);
  const h = Math.round((w * height) / width);
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { before: 80 }, keepNext: true,
      children: [new ImageRun({ type: "png", data: buf, transformation: { width: w, height: h },
        altText: { title: `Fig. ${number}`, description: caption, name: path.basename(file) } })],
    }),
    new Paragraph({
      alignment: AlignmentType.JUSTIFIED, spacing: { before: 40, after: 120 },
      children: [new TextRun({ text: `Fig. ${number}. `, font: FONT, size: SIZE.small }), ...runs(caption, { size: SIZE.small })],
    }),
  ];
}

function pngSize(buf) {
  return { width: buf.readUInt32BE(16), height: buf.readUInt32BE(20) };
}

const THIN = { style: BorderStyle.SINGLE, size: 4, color: "000000" };
const NONE = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };

// IEEE-style table: caption above (roman numeral + small caps title),
// rules above and below the header and at the bottom, 8 pt text.
// rows: array of arrays of strings; header: array of strings.
// widths: DXA per column, summing to the table width.
function table(number, title, header, rows, widths, note) {
  const total = widths.reduce((a, b) => a + b, 0);
  const cell = (text, i, { bold = false, top = NONE, bottom = NONE } = {}) => new TableCell({
    width: { size: widths[i], type: WidthType.DXA },
    verticalAlign: VerticalAlign.CENTER,
    margins: { top: 20, bottom: 20, left: 50, right: 50 },
    borders: { top, bottom, left: NONE, right: NONE },
    children: [new Paragraph({
      alignment: i === 0 ? AlignmentType.LEFT : AlignmentType.CENTER,
      children: runs(text, { size: SIZE.small, bold }),
    })],
  });
  const headerRow = new TableRow({ tableHeader: true, children: header.map((t, i) => cell(t, i, { top: THIN, bottom: THIN })) });
  const body = rows.map((r, ri) => new TableRow({
    cantSplit: true,
    children: r.map((t, i) => cell(t, i, { bottom: ri === rows.length - 1 ? THIN : NONE })),
  }));
  const out = [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120 }, keepNext: true,
      children: [new TextRun({ text: `TABLE ${ROMAN[number - 1]}`, font: FONT, size: SIZE.small })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, keepNext: true,
      children: [new TextRun({ text: title, font: FONT, size: SIZE.small, smallCaps: true })] }),
    new Table({ width: { size: total, type: WidthType.DXA }, columnWidths: widths, alignment: AlignmentType.CENTER,
      rows: [headerRow, ...body] }),
  ];
  if (note) {
    out.push(new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { before: 40, after: 120 },
      children: runs(note, { size: 14, italics: true }) }));
  } else {
    out.push(new Paragraph({ spacing: { after: 80 }, children: [] }));
  }
  return out;
}

function reference(n, text) {
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    indent: { left: 360, hanging: 360 },
    spacing: { after: 20 },
    children: [new TextRun({ text: `[${n}]\t`, font: FONT, size: SIZE.small }), ...runs(text, { size: SIZE.small })],
    tabStops: [{ type: TabStopType.LEFT, position: 360 }],
  });
}

const numbering = {
  config: [{
    reference: "bullets",
    levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 240, hanging: 160 } } } }],
  }],
};

const twoColumnSection = (children) => ({
  properties: { type: SectionType.CONTINUOUS, page: PAGE, column: { space: COL_GAP, count: 2 } },
  children,
});

module.exports = {
  FONT, PAGE, COL_WIDTH, SIZE, runs, para, runIn, bullet, heading, unnumberedHeading, subheading, equation,
  figure, table, reference, numbering, twoColumnSection,
};
