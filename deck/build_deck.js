// AutoReview Crew - hackathon submission deck generator.
// Build from repo root: node deck/build_deck.js
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const sharp = require("sharp");

const OUT_DIR = path.join(__dirname);
const PPTX = path.join(OUT_DIR, "AutoReview_Crew_Deck.pptx");
const COVER = path.join(OUT_DIR, "AutoReview_Crew_Cover.png");

const C = {
  ink: "062F35",
  teal: "0D9488",
  cyan: "14B8A6",
  mint: "B8F3EA",
  coral: "F45B69",
  amber: "F59E0B",
  blue: "2563EB",
  paper: "F7FBFA",
  panel: "E8F7F4",
  line: "BFE7E1",
  gray: "5F7472",
  white: "FFFFFF",
  red: "B4232A",
};

const HEAD = "Aptos Display";
const BODY = "Aptos";
const MONO = "Consolas";

function shadow() {
  return { type: "outer", color: "062F35", blur: 4, offset: 1, angle: 45, opacity: 0.12 };
}

function title(slide, kicker, claim, support) {
  slide.addText(kicker.toUpperCase(), {
    x: 0.52, y: 0.34, w: 2.8, h: 0.22, fontFace: BODY, fontSize: 8.5,
    bold: true, color: C.teal, margin: 0, breakLine: false,
  });
  slide.addText(claim, {
    x: 0.52, y: 0.58, w: 8.9, h: 0.58, fontFace: HEAD, fontSize: 26,
    bold: true, color: C.ink, margin: 0, fit: "shrink",
  });
  if (support) {
    slide.addText(support, {
      x: 0.54, y: 1.16, w: 8.75, h: 0.32, fontFace: BODY, fontSize: 11.5,
      color: C.gray, margin: 0,
    });
  }
}

function footer(slide, n) {
  slide.addText("AutoReview Crew | Band of Agents Hackathon", {
    x: 0.52, y: 5.28, w: 5.4, h: 0.18, fontFace: BODY, fontSize: 7.5,
    color: "6A8581", margin: 0,
  });
  slide.addText(String(n).padStart(2, "0"), {
    x: 9.05, y: 5.26, w: 0.38, h: 0.2, align: "right", fontFace: MONO,
    fontSize: 7.5, color: "6A8581", margin: 0,
  });
}

function box(slide, pptx, x, y, w, h, fill = C.white, line = C.line) {
  slide.addShape(pptx.ShapeType.rect, {
    x, y, w, h,
    rectRadius: 0.04,
    fill: { color: fill },
    line: { color: line, transparency: line === fill ? 100 : 0, pt: 0.6 },
    shadow: shadow(),
  });
}

function agentDot(slide, pptx, x, y, d, fill, label) {
  slide.addShape(pptx.ShapeType.ellipse, {
    x, y, w: d, h: d, fill: { color: fill }, line: { color: fill },
  });
  slide.addText(label, {
    x, y: y + d * 0.05, w: d, h: d * 0.9, align: "center", valign: "mid",
    fontFace: HEAD, fontSize: 13, bold: true, color: C.white, margin: 0,
  });
}

function smallTag(slide, text, x, y, w, fill = C.panel, color = C.teal) {
  slide.addShape("roundRect", {
    x, y, w, h: 0.23, rectRadius: 0.08,
    fill: { color: fill }, line: { color: fill },
  });
  slide.addText(text, {
    x, y: y + 0.015, w, h: 0.18, align: "center", valign: "mid",
    fontFace: BODY, fontSize: 7.5, bold: true, color, margin: 0,
  });
}

function bulletList(slide, items, x, y, w, fontSize = 10.5, color = C.gray) {
  items.forEach((item, i) => {
    const yy = y + i * 0.38;
    slide.addShape("ellipse", {
      x, y: yy + 0.08, w: 0.07, h: 0.07,
      fill: { color: C.teal }, line: { color: C.teal },
    });
    slide.addText(item, {
      x: x + 0.16, y: yy, w, h: 0.28, fontFace: BODY, fontSize,
      color, margin: 0, fit: "shrink",
    });
  });
}

function connector(slide, x1, y1, x2, y2, color = C.coral) {
  if (x2 <= x1) {
    return;
  }
  if (Math.abs(y2 - y1) < 0.01) {
    slide.addShape("line", {
      x: x1, y: y1, w: x2 - x1, h: 0,
      line: { color, pt: 1.5, beginArrowType: "none", endArrowType: "triangle" },
    });
    return;
  }

  const midX = x1 + (x2 - x1) * 0.48;
  slide.addShape("line", {
    x: x1, y: y1, w: midX - x1, h: 0,
    line: { color, pt: 1.3, beginArrowType: "none", endArrowType: "none" },
  });
  slide.addShape("line", {
    x: midX, y: Math.min(y1, y2), w: 0, h: Math.abs(y2 - y1),
    line: { color, pt: 1.3, beginArrowType: "none", endArrowType: "none" },
  });
  slide.addShape("line", {
    x: midX, y: y2, w: x2 - midX, h: 0,
    line: { color, pt: 1.5, beginArrowType: "none", endArrowType: "triangle" },
  });
}

async function makeCover() {
  const svg = `
  <svg width="1600" height="900" viewBox="0 0 1600 900" xmlns="http://www.w3.org/2000/svg">
    <rect width="1600" height="900" fill="#06343D"/>
    <path d="M0,720 C260,620 380,820 620,700 C860,580 1010,590 1220,680 C1400,758 1500,710 1600,640 L1600,900 L0,900 Z" fill="#0D9488" opacity="0.26"/>
    <path d="M0,250 C240,190 420,260 620,205 C850,142 1040,160 1220,240 C1400,320 1500,280 1600,230" fill="none" stroke="#14B8A6" stroke-width="4" opacity="0.55"/>
    <g transform="translate(455 126)">
      <circle cx="70" cy="70" r="58" fill="#0D9488"/>
      <circle cx="220" cy="70" r="58" fill="#14B8A6"/>
      <circle cx="370" cy="70" r="58" fill="#08756E"/>
      <circle cx="520" cy="70" r="58" fill="#F45B69"/>
      <text x="70" y="83" text-anchor="middle" font-family="Arial" font-size="42" font-weight="700" fill="#fff">LR</text>
      <text x="220" y="83" text-anchor="middle" font-family="Arial" font-size="42" font-weight="700" fill="#fff">CR</text>
      <text x="370" y="83" text-anchor="middle" font-family="Arial" font-size="42" font-weight="700" fill="#fff">SR</text>
      <text x="520" y="83" text-anchor="middle" font-family="Arial" font-size="42" font-weight="700" fill="#fff">TR</text>
    </g>
    <text x="800" y="380" text-anchor="middle" font-family="Arial" font-size="96" font-weight="800" fill="#fff">AutoReview Crew</text>
    <text x="800" y="455" text-anchor="middle" font-family="Arial" font-size="38" fill="#B8F3EA">AI agents that review code together and recruit help when needed</text>
    <text x="800" y="535" text-anchor="middle" font-family="Arial" font-size="28" fill="#9CD6CF">Band of Agents Hackathon | Track 2: Multi-Agent Software Development</text>
    <g transform="translate(462 645)">
      <rect x="0" y="0" width="210" height="56" rx="10" fill="#E8F7F4"/>
      <rect x="230" y="0" width="210" height="56" rx="10" fill="#E8F7F4"/>
      <rect x="460" y="0" width="210" height="56" rx="10" fill="#E8F7F4"/>
      <text x="105" y="36" text-anchor="middle" font-family="Arial" font-size="22" font-weight="700" fill="#0D9488">Band-native</text>
      <text x="335" y="36" text-anchor="middle" font-family="Arial" font-size="22" font-weight="700" fill="#0D9488">Cross-model</text>
      <text x="565" y="36" text-anchor="middle" font-family="Arial" font-size="22" font-weight="700" fill="#0D9488">Human-in-loop</text>
    </g>
  </svg>`;
  await sharp(Buffer.from(svg)).png().toFile(COVER);
}

(async () => {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  await makeCover();

  const pptx = new pptxgen();
  pptx.layout = "LAYOUT_16x9";
  pptx.author = "Kgotso Msiza";
  pptx.subject = "Band of Agents Hackathon submission";
  pptx.title = "AutoReview Crew";
  pptx.company = "AutoReview Crew";
  pptx.lang = "en-US";
  pptx.theme = {
    headFontFace: HEAD,
    bodyFontFace: BODY,
    lang: "en-US",
  };

  let s;

  // Slide 1
  s = pptx.addSlide();
  s.background = { color: C.ink };
  ["LR", "CR", "SR", "TR"].forEach((label, i) => {
    const colors = [C.teal, C.cyan, "08756E", C.coral];
    agentDot(s, pptx, 3.64 + i * 0.72, 0.74, 0.52, colors[i], label);
  });
  s.addText("AutoReview Crew", {
    x: 0.7, y: 1.66, w: 8.6, h: 0.65, align: "center",
    fontFace: HEAD, fontSize: 42, bold: true, color: C.white, margin: 0,
  });
  s.addText("AI agents that review code together and recruit help when needed", {
    x: 1.05, y: 2.46, w: 7.9, h: 0.36, align: "center",
    fontFace: BODY, fontSize: 17, color: C.mint, margin: 0,
  });
  s.addText("Four agents | Three model families | One Band room | 51-second live run", {
    x: 1.15, y: 3.08, w: 7.7, h: 0.28, align: "center",
    fontFace: BODY, fontSize: 12.5, italic: true, color: "9EDAD4", margin: 0,
  });
  s.addShape("line", { x: 3.1, y: 3.72, w: 3.8, h: 0, line: { color: C.coral, pt: 1.5 } });
  s.addText("Band of Agents Hackathon | Track 2: Multi-Agent Software Development | Kgotso Msiza", {
    x: 0.8, y: 4.72, w: 8.4, h: 0.24, align: "center",
    fontFace: BODY, fontSize: 10.5, color: "8CBFBA", margin: 0,
  });

  // Slide 2
  s = pptx.addSlide();
  s.background = { color: C.paper };
  title(s, "Problem", "Code review puts too many checks on one primary reviewer.", "Correctness, security, tests, maintainability, and merge risk often land in the same review window.");
  const pcols = [
    ["Bottleneck", "PRs wait for the busiest reviewer, not the best specialist."],
    ["Coverage gap", "Logic, security, and tests compete for one reviewer's attention."],
    ["Weak audit trail", "The merge decision often loses who checked what and why."],
  ];
  pcols.forEach((pcol, i) => {
    const x = 0.58 + i * 3.05;
    box(s, pptx, x, 1.72, 2.72, 2.8, C.white);
    s.addText(String(i + 1).padStart(2, "0"), {
      x: x + 0.2, y: 1.96, w: 0.42, h: 0.26, fontFace: MONO,
      fontSize: 11, color: C.coral, bold: true, margin: 0,
    });
    s.addText(pcol[0], {
      x: x + 0.2, y: 2.34, w: 2.25, h: 0.34, fontFace: HEAD,
      fontSize: 17, color: C.ink, bold: true, margin: 0,
    });
    s.addText(pcol[1], {
      x: x + 0.2, y: 2.92, w: 2.25, h: 0.82, fontFace: BODY,
      fontSize: 12, color: C.gray, margin: 0, fit: "shrink",
    });
  });
  s.addText("AutoReview Crew turns review into a coordinated team workflow.", {
    x: 0.58, y: 4.86, w: 8.8, h: 0.28, fontFace: HEAD,
    fontSize: 15, color: C.teal, bold: true, italic: true, margin: 0,
  });
  footer(s, 2);

  // Slide 3
  s = pptx.addSlide();
  s.background = { color: C.paper };
  title(s, "Hackathon fit", "Built around Band-native multi-agent software development.", "The workflow combines visible agent coordination, PR review, live recruitment, and partner model usage.");
  const fit = [
    ["Band-native workflow", "4 agents coordinate in one shared room", C.teal],
    ["Track 2", "PR review, tests, merge preparation", C.blue],
    ["AI/ML API", "Lead, Correctness, Test agents", C.cyan],
    ["Featherless AI", "Security Reviewer on Qwen2.5-72B", C.coral],
  ];
  fit.forEach((row, i) => {
    const x = 0.65 + (i % 2) * 4.45;
    const y = 1.78 + Math.floor(i / 2) * 1.48;
    box(s, pptx, x, y, 4.0, 1.12, C.white);
    s.addShape("rect", { x, y, w: 0.12, h: 1.12, fill: { color: row[2] }, line: { color: row[2] } });
    s.addText(row[0], { x: x + 0.3, y: y + 0.18, w: 3.45, h: 0.24, fontFace: HEAD, fontSize: 14, bold: true, color: C.ink, margin: 0 });
    s.addText(row[1], { x: x + 0.3, y: y + 0.54, w: 3.45, h: 0.3, fontFace: BODY, fontSize: 11.5, color: C.gray, margin: 0 });
  });
  s.addText("Positioning: a Band-native software review room where agents hand off work, recruit specialists, and escalate risky changes with an audit trail.", {
    x: 0.7, y: 4.78, w: 8.55, h: 0.36, fontFace: BODY, fontSize: 11.3,
    color: C.gray, margin: 0,
  });
  footer(s, 3);

  // Slide 4
  s = pptx.addSlide();
  s.background = { color: C.paper };
  title(s, "Architecture", "Band is the coordination layer, not the output channel.", "Every assignment, report, recruitment, and final escalation is routed through the shared room.");
  s.addShape("rect", { x: 1.68, y: 1.58, w: 5.94, h: 3.3, fill: { color: "DFF6F2", transparency: 40 }, line: { color: C.line, pt: 1 } });
  const nodes = [
    ["Human", "starts review", 0.62, 2.64, "475569"],
    ["Lead", "delegates + gates", 2.15, 2.64, C.teal],
    ["Correctness", "logic review", 4.0, 1.72, C.cyan],
    ["Security", "risk review", 4.0, 3.52, "08756E"],
    ["Test", "recruited live", 6.02, 2.64, C.coral],
    ["GitHub PR", "comment posted", 7.82, 2.64, C.blue],
  ];
  nodes.forEach(([name, sub, x, y, color]) => {
    box(s, pptx, x, y, 1.32, 0.82, C.white);
    s.addText(name, { x: x + 0.08, y: y + 0.14, w: 1.15, h: 0.22, align: "center", fontFace: HEAD, fontSize: 10.8, bold: true, color, margin: 0 });
    s.addText(sub, { x: x + 0.08, y: y + 0.42, w: 1.15, h: 0.2, align: "center", fontFace: BODY, fontSize: 7.8, color: C.gray, margin: 0 });
  });
  connector(s, 1.95, 3.05, 2.14, 3.05);
  connector(s, 3.5, 2.86, 4.0, 2.1);
  connector(s, 3.5, 3.22, 4.0, 3.95);
  connector(s, 5.36, 2.14, 6.02, 2.86);
  connector(s, 5.36, 3.94, 6.02, 3.22);
  connector(s, 7.35, 3.05, 7.82, 3.05);
  s.addText("Band room: shared context, @mentions, participant recruitment, event audit trail", {
    x: 2.0, y: 4.68, w: 5.6, h: 0.24, align: "center", fontFace: BODY,
    fontSize: 10.2, color: C.teal, bold: true, margin: 0,
  });
  footer(s, 4);

  // Slide 5
  s = pptx.addSlide();
  s.background = { color: C.paper };
  title(s, "Live run", "The submitted video shows the whole workflow in about 51 seconds.", "One Lead delegation, specialist reports, a live recruitment, and a final escalation.");
  const beats = [
    ["13:02:22", "Human", "@Lead Reviewer please review the code change", "475569"],
    ["13:02:23", "Lead", "Delegates once to Correctness + Security", C.teal],
    ["13:02:33", "Correctness", "Finds division by zero + mutable default", C.cyan],
    ["13:02:48", "Security", "Finds hardcoded key, SQL injection, validation gap", "08756E"],
    ["13:02:55", "Lead", "Recruits Test Reviewer through Band", C.coral],
    ["13:03:08", "Test", "Posts pytest coverage", C.coral],
    ["13:03:13", "Lead", "Final verdict: ESCALATE_TO_HUMAN", C.teal],
  ];
  beats.forEach((b, i) => {
    const y = 1.62 + i * 0.49;
    s.addText(b[0], { x: 0.62, y, w: 0.92, h: 0.22, fontFace: MONO, fontSize: 8.6, color: C.gray, margin: 0 });
    s.addShape("rect", { x: 1.72, y: y - 0.06, w: 7.6, h: 0.34, fill: { color: C.white }, line: { color: C.line, pt: 0.4 } });
    s.addShape("rect", { x: 1.72, y: y - 0.06, w: 0.08, h: 0.34, fill: { color: b[3] }, line: { color: b[3] } });
    s.addText(b[1], { x: 1.92, y, w: 1.08, h: 0.2, fontFace: HEAD, fontSize: 9.3, bold: true, color: b[3], margin: 0 });
    s.addText(b[2], { x: 3.0, y, w: 6.15, h: 0.2, fontFace: BODY, fontSize: 9.3, color: C.gray, margin: 0, fit: "shrink" });
  });
  footer(s, 5);

  // Slide 6
  s = pptx.addSlide();
  s.background = { color: C.ink };
  s.addText("The moment: agents hiring agents", {
    x: 0.6, y: 0.58, w: 8.8, h: 0.54, align: "center",
    fontFace: HEAD, fontSize: 30, bold: true, color: C.white, margin: 0,
  });
  s.addText("The Test Reviewer is not in the room at the start. The Lead discovers and recruits it only when the gate requires tests.", {
    x: 1.05, y: 1.24, w: 7.9, h: 0.36, align: "center",
    fontFace: BODY, fontSize: 12.2, color: C.mint, margin: 0,
  });
  const steps = [
    ["Gate", "No final verdict without a [TESTS] report"],
    ["Search", "band_lookup_peers()"],
    ["Recruit", "band_add_participant(test-reviewer)"],
    ["Assign", "@Test Reviewer please review coverage"],
  ];
  steps.forEach((st, i) => {
    const x = 0.62 + i * 2.33;
    s.addShape("rect", { x, y: 2.2, w: 1.86, h: 1.18, fill: { color: "0B4A52" }, line: { color: "0B4A52" } });
    s.addText(st[0], { x: x + 0.12, y: 2.38, w: 1.62, h: 0.24, fontFace: HEAD, fontSize: 13, bold: true, color: C.white, align: "center", margin: 0 });
    s.addText(st[1], { x: x + 0.12, y: 2.78, w: 1.62, h: 0.32, fontFace: BODY, fontSize: 8.8, color: C.mint, align: "center", margin: 0, fit: "shrink" });
    if (i < 3) connector(s, x + 1.93, 2.8, x + 2.25, 2.8, C.coral);
  });
  agentDot(s, pptx, 4.72, 3.82, 0.68, C.coral, "TR");
  s.addText("This is the originality beat: the workflow adapts by adding a new specialist, inside Band, without human intervention.", {
    x: 1.08, y: 4.68, w: 7.85, h: 0.3, align: "center",
    fontFace: HEAD, fontSize: 13.3, bold: true, color: C.white, margin: 0,
  });

  // Slide 7
  s = pptx.addSlide();
  s.background = { color: C.paper };
  title(s, "Review output", "Different specialists catch different classes of risk.", "The Lead aggregates the reports instead of flattening everything into one generic model answer.");
  const findings = [
    ["Security", "CRITICAL", "Hardcoded Stripe API key", C.red],
    ["Security", "HIGH", "SQL injection", C.red],
    ["Correctness", "HIGH", "Division by zero", C.amber],
    ["Correctness", "MEDIUM", "Mutable default argument", C.amber],
    ["Test", "TESTS", "Pytest coverage for risky paths", C.coral],
  ];
  findings.forEach((f, i) => {
    const y = 1.62 + i * 0.64;
    box(s, pptx, 0.72, y, 8.6, 0.48, C.white, C.line);
    smallTag(s, f[0], 0.95, y + 0.125, 0.88, C.panel, C.teal);
    smallTag(s, f[1], 2.0, y + 0.125, 0.75, "FDECEC", f[3]);
    s.addText(f[2], { x: 3.0, y: y + 0.13, w: 5.8, h: 0.2, fontFace: BODY, fontSize: 10.6, color: C.gray, margin: 0 });
  });
  s.addText("Final decision: ESCALATE_TO_HUMAN because a leaked secret and injection risk should not merge on automation alone.", {
    x: 0.72, y: 4.92, w: 8.4, h: 0.24, align: "center",
    fontFace: HEAD, fontSize: 12.3, bold: true, color: C.red, margin: 0,
  });
  footer(s, 7);

  // Slide 8
  s = pptx.addSlide();
  s.background = { color: C.paper };
  title(s, "Reliability", "The build is hardened for live multi-agent messiness.", "It is designed to recover from the failure modes we saw while building, not just succeed in one perfect run.");
  const hardening = [
    ["Current-round filter", "Old reports from reused rooms cannot satisfy a new review."],
    ["All-page context fetch", "The Lead sees the whole room context, not just page 1."],
    ["One report per trigger", "Duplicate tool-call races do not create spam."],
    ["Test gate", "No final verdict until pytest functions appear."],
    ["Started-signal retry logic", "Working reviewers get more time; missing reviewers get nudged."],
    ["Human escalation rail", "Missing specialists or critical findings force human review."],
  ];
  hardening.forEach((h, i) => {
    const x = 0.65 + (i % 2) * 4.45;
    const y = 1.6 + Math.floor(i / 2) * 1.0;
    box(s, pptx, x, y, 4.0, 0.72, C.white);
    s.addText(h[0], { x: x + 0.18, y: y + 0.12, w: 3.62, h: 0.18, fontFace: HEAD, fontSize: 10.8, bold: true, color: C.ink, margin: 0 });
    s.addText(h[1], { x: x + 0.18, y: y + 0.38, w: 3.62, h: 0.16, fontFace: BODY, fontSize: 8.6, color: C.gray, margin: 0, fit: "shrink" });
  });
  s.addText("Architecture choice: deterministic coordination; LLMs do specialist review and final wording.", {
    x: 0.72, y: 4.86, w: 8.4, h: 0.24, align: "center",
    fontFace: BODY, fontSize: 11.2, bold: true, color: C.teal, margin: 0,
  });
  footer(s, 8);

  // Slide 9
  s = pptx.addSlide();
  s.background = { color: C.paper };
  title(s, "Business value", "A review crew is faster, safer, and more auditable than a single assistant.", "The same Band pattern can expand from PR review into release, compliance, and incident workflows.");
  box(s, pptx, 0.65, 1.66, 4.08, 2.75, C.white);
  s.addText("For engineering teams", { x: 0.9, y: 1.9, w: 3.55, h: 0.25, fontFace: HEAD, fontSize: 14.5, bold: true, color: C.ink, margin: 0 });
  bulletList(s, [
    "Specialist coverage on every risky diff",
    "Human escalation for critical issues",
    "Audit trail for who checked what",
    "Faster merge preparation for routine changes",
  ], 0.9, 2.35, 3.45, 9.8);
  box(s, pptx, 5.05, 1.66, 4.08, 2.75, C.white);
  s.addText("Why it can grow", { x: 5.3, y: 1.9, w: 3.55, h: 0.25, fontFace: HEAD, fontSize: 14.5, bold: true, color: C.ink, margin: 0 });
  bulletList(s, [
    "Add performance, docs, compliance specialists",
    "Use org agent registry for reusable expertise",
    "Post final reports to GitHub or ticket systems",
    "Apply the same pattern to high-stakes workflows",
  ], 5.3, 2.35, 3.45, 9.8);
  footer(s, 9);

  // Slide 10
  s = pptx.addSlide();
  s.background = { color: C.ink };
  ["LR", "CR", "SR", "TR"].forEach((label, i) => {
    const colors = [C.teal, C.cyan, "08756E", C.coral];
    agentDot(s, pptx, 3.64 + i * 0.72, 0.72, 0.52, colors[i], label);
  });
  s.addText("AutoReview Crew", {
    x: 0.78, y: 1.62, w: 8.4, h: 0.52, align: "center",
    fontFace: HEAD, fontSize: 34, bold: true, color: C.white, margin: 0,
  });
  s.addText("Specialist AI reviewers that work in parallel, recruit help when needed, and know when to call a human.", {
    x: 1.1, y: 2.42, w: 7.8, h: 0.52, align: "center",
    fontFace: BODY, fontSize: 15, color: C.mint, margin: 0, fit: "shrink",
  });
  s.addText("Band turns separate agents into a review crew.", {
    x: 1.2, y: 3.34, w: 7.6, h: 0.3, align: "center",
    fontFace: HEAD, fontSize: 16, bold: true, color: C.white, margin: 0,
  });
  s.addText("Built solo with agentic coding | MIT licensed | Track 2", {
    x: 1.2, y: 4.34, w: 7.6, h: 0.25, align: "center",
    fontFace: BODY, fontSize: 11, color: "8CBFBA", margin: 0,
  });

  await pptx.writeFile({ fileName: PPTX });
  console.log(`Wrote ${PPTX}`);
  console.log(`Wrote ${COVER}`);
})();
