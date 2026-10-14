// Builds roadmap_banque_du_vexin.pptx from use_cases.csv.
// Fictional bank. Run: node docs/roadmap/build_deck.js  (needs `npm i pptxgenjs`)
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const HERE = __dirname;
const OUT = path.join(HERE, "roadmap_banque_du_vexin.pptx");

// ---------------------------------------------------------------- data
const rows = fs.readFileSync(path.join(HERE, "use_cases.csv"), "utf8").trim().split("\n");
const head = rows.shift().split(",");
const UC = rows.map((r) => {
  const v = r.split(",");
  const o = Object.fromEntries(head.map((h, i) => [h, v[i]]));
  ["impact", "effort", "risque", "vague"].forEach((k) => (o[k] = Number(o[k])));
  o.score = 2 * o.impact - o.effort - o.risque;
  return o;
});

// ---------------------------------------------------------------- theme
const THEME = {
  name: "Vexin Conformite",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "1B2333", lt1: "FFFFFF", dk2: "14213D", lt2: "EEF2F5",
    accent1: "0F766E", accent2: "D97706", accent3: "B42318", accent4: "5B6B7F",
    accent5: "99D5CC", accent6: "F3C98B", hlink: "0F766E", folHlink: "5B6B7F",
  },
};
const K = THEME.colors;
const INK = K.dk1, NAVY = K.dk2, TEAL = K.accent1, AMBER = K.accent2, RED = K.accent3, SLATE = K.accent4;
const MINT = K.accent5, SAND = K.accent6, MIST = K.lt2;

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625 in
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "Feuille de route Data & IA - Banque du Vexin (cas fictif)";
pres.author = "Seifeddine Ben Rhouma";
pres.company = "Cas fictif";

const FOOT = "Banque du Vexin est une banque fictive. Cas d'école construit pour le projet compliance-copilot.";

pres.defineSlideMaster({
  title: "DARK",
  background: { color: NAVY },
  objects: [{ text: { text: FOOT, options: { x: 0.5, y: 5.2, w: 8.2, h: 0.3, fontSize: 9, color: "A9B4C6", fontFace: "Calibri" } } }],
  slideNumber: { x: 9.1, y: 5.2, w: 0.5, h: 0.3, fontSize: 9, color: "A9B4C6", fontFace: "Calibri" },
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: "FFFFFF" },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 9, h: 0.75, fontFace: "Cambria", fontSize: 24, bold: true, color: NAVY, margin: 0, valign: "middle", align: "left" }, text: "" } },
    { text: { text: FOOT, options: { x: 0.5, y: 5.2, w: 8.2, h: 0.3, fontSize: 9, color: SLATE, fontFace: "Calibri" } } },
  ],
  slideNumber: { x: 9.1, y: 5.2, w: 0.5, h: 0.3, fontSize: 9, color: SLATE, fontFace: "Calibri" },
});

const tb = (o) => Object.assign({ isTextBox: true, fontFace: "Calibri", color: INK, margin: 0 }, o);

// Slide 1 ------------------------------------------------------------- title
pres.addSection({ title: "Ouverture" });
let s = pres.addSlide({ masterName: "DARK", sectionTitle: "Ouverture" });
s.addText("CAS FICTIF · DATA & IA", tb({ x: 0.6, y: 0.7, w: 6, h: 0.35, fontSize: 12, bold: true, color: MINT, charSpacing: 3 }));
s.addText("Feuille de route Data & IA 2027", tb({ x: 0.6, y: 1.15, w: 8.5, h: 0.9, fontSize: 38, bold: true, color: "FFFFFF", fontFace: "Cambria" }));
s.addText("Banque du Vexin : huit cas d'usage notés sur l'impact, l'effort et le risque réglementaire",
  tb({ x: 0.6, y: 2.1, w: 7.8, h: 0.8, fontSize: 18, color: "D5DDE8" }));
const kpis = [["8", "cas d'usage évalués"], ["3", "vagues de déploiement"], ["2", "cas haut risque AI Act"]];
kpis.forEach(([n, l], i) => {
  const x = 0.6 + i * 2.6;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 3.35, w: 2.3, h: 1.25, fill: { color: "1E3157" }, line: { color: "1E3157" }, rectRadius: 0.08, objectName: `kpi${i}` });
  s.addText(n, tb({ x: x + 0.2, y: 3.45, w: 1.9, h: 0.65, fontSize: 32, bold: true, color: MINT, fontFace: "Cambria" }));
  s.addText(l, tb({ x: x + 0.2, y: 4.1, w: 1.9, h: 0.4, fontSize: 13, color: "FFFFFF" }));
});
s.addNotes("Livrable de cadrage pour une banque et assurance fictive. Les notes sont des hypothèses de travail, pas des mesures.");

// Slide 2 ---------------------------------------------------------- synthèse
pres.addSection({ title: "Synthèse" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Synthèse" });
s.addText("IA interne et citée d'abord, haut risque ensuite", { placeholder: "title" });
const msgs = [
  [TEAL, "1", "Vague 1 : gains rapides à faible risque", "Copilote conformité, registre DORA et synthèse d'incidents : usages internes, sources citées, refus sans source."],
  [AMBER, "2", "Vague 2 : métiers, sous contrôle humain", "Tri des réclamations IARD, assistant conseiller et fraude : l'IA propose, un humain décide."],
  [RED, "3", "Vague 3 : haut risque, après le socle", "Crédit et tarification santé relèvent de l'annexe III : obligations applicables au 2 décembre 2027."],
];
msgs.forEach(([c, n, t, d], i) => {
  const y = 1.3 + i * 1.22;
  s.addShape(pres.shapes.OVAL, { x: 0.5, y: y + 0.05, w: 0.6, h: 0.6, fill: { color: c }, line: { color: c }, objectName: `num${i}` });
  s.addText(n, tb({ x: 0.5, y: y + 0.05, w: 0.6, h: 0.6, fontSize: 20, bold: true, color: "FFFFFF", align: "center", valign: "middle" }));
  s.addText(t, tb({ x: 1.35, y, w: 7.9, h: 0.4, fontSize: 18, bold: true, color: NAVY }));
  s.addText(d, tb({ x: 1.35, y: y + 0.42, w: 7.9, h: 0.6, fontSize: 14, color: INK }));
});

// Slide 3 ------------------------------------------------------- calendrier
pres.addSection({ title: "Contexte" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Contexte" });
s.addText("Le calendrier réglementaire fixe l'ordre", { placeholder: "title" });
const events = [
  ["17 janv. 2025", "DORA s'applique", "Risque TIC, incidents, prestataires", TEAL],
  ["2 févr. 2025", "AI Act : interdictions", "et culture de l'IA (art. 4)", SLATE],
  ["2 août 2025", "AI Act : modèles GPAI", "gouvernance, sanctions", SLATE],
  ["2 août 2026", "AI Act : transparence", "art. 50, IA en interaction", AMBER],
  ["2 déc. 2027", "Haut risque annexe III", "crédit, santé (Omnibus)", RED],
  ["2 août 2028", "Haut risque annexe I", "produits réglementés", SLATE],
];
const x0 = 0.9, x1 = 9.1, ly = 2.55;
s.addShape(pres.shapes.LINE, { x: x0, y: ly, w: x1 - x0, h: 0, line: { color: "C3CCD7", width: 2 }, objectName: "timeline" });
events.forEach(([d, t, sub, c], i) => {
  const cx = x0 + 0.15 + i * ((x1 - x0 - 0.3) / (events.length - 1));
  s.addShape(pres.shapes.OVAL, { x: cx - 0.13, y: ly - 0.13, w: 0.26, h: 0.26, fill: { color: c }, line: { color: "FFFFFF", width: 2 }, objectName: `dot${i}` });
  const up = i % 2 === 0;
  s.addText(d, tb({ x: cx - 0.75, y: up ? 1.35 : 2.85, w: 1.5, h: 0.3, fontSize: 12, bold: true, color: c, align: "center" }));
  s.addText(t, tb({ x: cx - 0.8, y: up ? 1.65 : 3.15, w: 1.6, h: 0.5, fontSize: 12, bold: true, color: NAVY, align: "center", valign: "top" }));
  s.addText(sub, tb({ x: cx - 0.8, y: up ? 2.0 : 3.48, w: 1.6, h: 0.4, fontSize: 10, color: SLATE, align: "center", valign: "top" }));
});
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y: 4.3, w: 9, h: 0.65, fill: { color: MIST }, line: { color: MIST }, rectRadius: 0.06, objectName: "callout" });
s.addText("Le Digital Omnibus (règlement (UE) 2026/1744) a repoussé l'annexe III du 2 août 2026 au 2 décembre 2027 : 14 mois pour bâtir le socle de conformité.",
  tb({ x: 0.7, y: 4.33, w: 8.6, h: 0.6, fontSize: 13, color: NAVY, valign: "middle" }));

// Slide 4 --------------------------------------------------------- méthode
pres.addSection({ title: "Analyse" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Analyse" });
s.addText("Trois axes de notation, le risque pèse autant que l'effort", { placeholder: "title" });
const axes = [
  [TEAL, "Impact (1-5)", "Gain métier : temps économisé, pertes évitées, qualité de service. Compté double."],
  [AMBER, "Effort (1-5)", "Données disponibles, intégration au SI, conduite du changement."],
  [RED, "Risque (1-5)", "Classification AI Act, données personnelles (RGPD), exposition client, dépendance fournisseur (DORA)."],
];
axes.forEach(([c, t, d], i) => {
  const x = 0.5 + i * 3.05;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.3, w: 2.85, h: 2.2, fill: { color: MIST }, line: { color: MIST }, rectRadius: 0.06, objectName: `axis${i}` });
  s.addShape(pres.shapes.OVAL, { x: x + 0.25, y: 1.5, w: 0.4, h: 0.4, fill: { color: c }, line: { color: c }, objectName: `axisdot${i}` });
  s.addText(t, tb({ x: x + 0.8, y: 1.5, w: 1.9, h: 0.4, fontSize: 16, bold: true, color: NAVY, valign: "middle" }));
  s.addText(d, tb({ x: x + 0.25, y: 2.05, w: 2.4, h: 1.3, fontSize: 13, color: INK, valign: "top" }));
});
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y: 3.8, w: 9, h: 1.05, fill: { color: NAVY }, line: { color: NAVY }, rectRadius: 0.06, objectName: "formula" });
s.addText([
  { text: "Priorité = 2 × impact − effort − risque", options: { fontSize: 20, bold: true, color: "FFFFFF", fontFace: "Cambria", breakLine: true } },
  { text: "Un cas haut risque n'est lancé qu'une fois le socle en place : registre des risques, évaluation continue, journal d'audit.", options: { fontSize: 13, color: "D5DDE8" } },
], tb({ x: 0.75, y: 3.85, w: 8.5, h: 0.95, valign: "middle" }));

// Slide 5 ----------------------------------------------------------- table
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Analyse" });
s.addText("Huit cas notés : le copilote conformité en tête", { placeholder: "title" });
const sorted = [...UC].sort((a, b) => b.score - a.score || a.id.localeCompare(b.id));
const hdr = ["Cas d'usage", "Impact", "Effort", "Risque", "Priorité", "AI Act", "Vague"].map((t) => ({
  text: t, options: { bold: true, color: "FFFFFF", fill: { color: NAVY }, fontSize: 11, align: t === "Cas d'usage" || t === "AI Act" ? "left" : "center" } }));
const vagueColor = { 1: TEAL, 2: AMBER, 3: RED };
const body = sorted.map((u, i) => {
  const f = { color: i % 2 ? "FFFFFF" : "F6F8FA" };
  const c = (t, o = {}) => ({ text: String(t), options: Object.assign({ fill: f, fontSize: 11, color: INK, align: "center" }, o) });
  return [c(u.cas_usage, { align: "left", bold: true }), c(u.impact), c(u.effort), c(u.risque),
    c(u.score, { bold: true, color: u.score >= 3 ? TEAL : u.score <= 1 ? RED : INK }),
    c(u.classification_ai_act, { align: "left", fontSize: 10 }), c(u.vague, { bold: true, color: vagueColor[u.vague] })];
});
s.addTable([hdr, ...body], { x: 0.5, y: 1.2, w: 9, colW: [2.75, 0.7, 0.7, 0.7, 0.8, 2.75, 0.6], rowH: 0.42, fontFace: "Calibri",
  border: { type: "solid", pt: 0.5, color: "DDE3EA" }, valign: "middle", margin: [0, 0.06, 0, 0.06] });

// Slide 6 ---------------------------------------------------------- matrice
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Analyse" });
s.addText("Impact et effort, la taille du cercle donne le risque", { placeholder: "title" });
const MX = 0.9, MY = 1.2, MW = 5.4, MH = 3.7;
const qx = (e) => MX + ((e - 0.5) / 5) * MW;
const qy = (im) => MY + MH - ((im - 0.5) / 5) * MH;
const SX = qx(3.5), SY = qy(2.5); // quick wins: effort <= 3 and impact >= 3
s.addShape(pres.shapes.RECTANGLE, { x: MX, y: MY, w: SX - MX, h: SY - MY, fill: { color: "E3F2EF" }, line: { color: "E3F2EF" }, objectName: "quickwins" });
s.addShape(pres.shapes.RECTANGLE, { x: SX, y: MY, w: MX + MW - SX, h: SY - MY, fill: { color: "FDF3E3" }, line: { color: "FDF3E3" }, objectName: "bigbets" });
s.addShape(pres.shapes.RECTANGLE, { x: MX, y: SY, w: MW, h: MY + MH - SY, fill: { color: "F6F8FA" }, line: { color: "F6F8FA" }, objectName: "low" });
s.addText("Gains rapides", tb({ x: MX + 0.1, y: SY - 0.32, w: 2, h: 0.26, fontSize: 11, bold: true, color: TEAL }));
s.addText("Paris stratégiques", tb({ x: SX + 0.1, y: SY - 0.32, w: 2, h: 0.26, fontSize: 11, bold: true, color: AMBER }));
s.addText("Faible impact : aucun cas retenu dans cette sélection", tb({ x: MX + 0.1, y: MY + MH - 0.4, w: 4.5, h: 0.3, fontSize: 11, italic: true, color: SLATE }));
s.addText("Effort →", tb({ x: MX + MW - 1, y: MY + MH + 0.05, w: 1, h: 0.25, fontSize: 11, color: SLATE, align: "right" }));
s.addText("Impact →", tb({ x: MX - 0.75, y: MY + 0.2, w: 0.7, h: 0.5, fontSize: 11, color: SLATE, align: "right" }));
const groups = {};
UC.forEach((u) => (groups[`${u.effort}-${u.impact}`] = (groups[`${u.effort}-${u.impact}`] || []).concat(u)));
Object.values(groups).forEach((g) => g.forEach((u, k) => {
  const d = 0.26 + u.risque * 0.06;
  const cx = qx(u.effort) + (k - (g.length - 1) / 2) * 0.7;
  const cxx = cx;
  const cyy = qy(u.impact);
  const col = vagueColor[u.vague];
  s.addShape(pres.shapes.OVAL, { x: cxx - d / 2, y: cyy - d / 2, w: d, h: d, fill: { color: col }, line: { color: "FFFFFF", width: 1 }, objectName: `bubble_${u.id}` });
  s.addText(u.id.replace("UC", ""), tb({ x: cxx - d / 2, y: cyy - d / 2, w: d, h: d, fontSize: 11, bold: true, color: "FFFFFF", align: "center", valign: "middle" }));
}));
s.addText(UC.map((u, i) => ({ text: `${u.id.replace("UC", "")}  ${u.cas_usage}`, options: { breakLine: i < UC.length - 1, color: vagueColor[u.vague], bold: true } })),
  tb({ x: 6.65, y: 1.25, w: 2.9, h: 2.9, fontSize: 12, valign: "top", paraSpaceAfter: 4 }));
s.addText("Couleur : vague 1 vert, 2 orange, 3 rouge.", tb({ x: 6.65, y: 4.3, w: 2.9, h: 0.5, fontSize: 10, color: SLATE }));

// Slide 7 ------------------------------------------------------- roadmap
pres.addSection({ title: "Plan" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Plan" });
s.addText("Trois vagues en 2027, haut risque prêt en décembre", { placeholder: "title" });
const quarters = ["T1 2027", "T2 2027", "T3 2027", "T4 2027"];
const GX = 3.2, GW = 6.3, GY = 1.25;
quarters.forEach((q, i) => s.addText(q, tb({ x: GX + i * (GW / 4), y: GY, w: GW / 4, h: 0.3, fontSize: 12, bold: true, color: SLATE, align: "center" })));
const bars = [
  ["Socle commun (données, éval, audit)", 0, 1.5, NAVY],
  ["Copilote conformité", 0, 1, TEAL], ["Registre DORA des prestataires", 0, 1, TEAL], ["Synthèse des incidents TIC", 0.5, 1.5, TEAL],
  ["Tri des réclamations IARD", 1, 2.5, AMBER], ["Assistant conseiller", 1.5, 3, AMBER], ["Fraude aux paiements", 2, 4, AMBER],
  ["Crédit et santé (haut risque)", 2, 4, RED],
];
bars.forEach(([label, a, b, c], i) => {
  const y = GY + 0.4 + i * 0.43;
  s.addText(label, tb({ x: 0.5, y, w: 2.6, h: 0.34, fontSize: 12, color: INK, valign: "middle", bold: i === 0 }));
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: GX + a * (GW / 4) + 0.04, y: y + 0.04, w: (b - a) * (GW / 4) - 0.08, h: 0.26, fill: { color: c }, line: { color: c }, rectRadius: 0.05, objectName: `bar${i}` });
});
const dx = GX + 3.67 * (GW / 4);
s.addShape(pres.shapes.LINE, { x: dx, y: GY + 0.35, w: 0, h: 3.5, line: { color: RED, width: 1.5, dashType: "dash" }, objectName: "deadline" });
s.addText("2 déc.", tb({ x: dx + 0.06, y: GY + 0.33, w: 0.6, h: 0.22, fontSize: 10, bold: true, color: RED }));

// Slide 8 ------------------------------------------------- décisions
pres.addSection({ title: "Décisions" });
s = pres.addSlide({ masterName: "DARK", sectionTitle: "Décisions" });
s.addText("Décisions demandées au comité", tb({ x: 0.6, y: 0.45, w: 8.8, h: 0.7, fontSize: 30, bold: true, color: "FFFFFF", fontFace: "Cambria" }));
const asks = [
  ["Lancer la vague 1", "Copilote, registre DORA et synthèse d'incidents, budget socle inclus."],
  ["Adopter le socle commun", "Contrats de données, évaluation en CI, registre des risques et journal d'audit pour tout projet IA."],
  ["Nommer les responsables", "Un propriétaire métier et un responsable des risques par cas d'usage, revue trimestrielle."],
];
asks.forEach(([t, d], i) => {
  const y = 1.4 + i * 1.05;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y, w: 5.6, h: 0.88, fill: { color: "1E3157" }, line: { color: "1E3157" }, rectRadius: 0.06, objectName: `ask${i}` });
  s.addText(t, tb({ x: 0.85, y: y + 0.08, w: 5.2, h: 0.35, fontSize: 16, bold: true, color: MINT }));
  s.addText(d, tb({ x: 0.85, y: y + 0.43, w: 5.2, h: 0.4, fontSize: 12, color: "FFFFFF" }));
});
s.addText("Indicateurs suivis", tb({ x: 6.6, y: 1.4, w: 3, h: 0.35, fontSize: 16, bold: true, color: SAND }));
s.addText([
  { text: "Taux de refus hors périmètre", options: { bullet: true, breakLine: true } },
  { text: "Réponses citant la bonne source", options: { bullet: true, breakLine: true } },
  { text: "Réclamations à revoir non manquées", options: { bullet: true, breakLine: true } },
  { text: "Coût et latence par requête", options: { bullet: true, breakLine: true } },
  { text: "Intégrité du journal d'audit", options: { bullet: true } },
], tb({ x: 6.6, y: 1.85, w: 2.9, h: 2.4, fontSize: 13, color: "FFFFFF", paraSpaceAfter: 6, valign: "top" }));

pres.writeFile({ fileName: OUT }).then(async () => {
  for (const p of [process.env.APPLY_THEME, "/mnt/skills/public/pptx/scripts/apply_theme.js"]) {
    if (p && fs.existsSync(p)) {
      await require(p).applyTheme(OUT, THEME);
      break;
    }
  }
  console.log("wrote", OUT);
});
