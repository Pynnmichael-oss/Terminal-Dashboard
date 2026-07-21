const T4_KEY = "gp_t4Schedule";
const GRADE_PRODUCT = {"4D":"REG","3D":"PREM","75":"ULSD"};

function parseT4Paste(text){
  const lines = text.trim().split('\n').filter(l => l.trim());
  const batches = [];
  lines.forEach(line => {
    const cols = line.split('\t');
    if (cols.length < 14) return;
    if (/^Start Date/i.test(cols[0])) return; // skip header row
    const dt = cols[0], line_ = cols[1], batchCode = cols[5];
    const vol = parseFloat((cols[11]||'').replace(/,/g,''));
    const rate = parseFloat((cols[13]||'').replace(/,/g,''));
    if (!batchCode || isNaN(vol) || isNaN(rate)) return;
    const parts = batchCode.split('-');
    const grade = parts[2];
    if (!GRADE_PRODUCT[grade]) return; // unmapped grade skipped
    batches.push({s: normalizeDateTime(dt), line: line_, code: batchCode, vol, rate});
  });
  return batches;
}
function normalizeDateTime(s){
  // "07/21/26 00:35" -> "2026-07-21T00:35:00"
  const [d,t] = s.split(' ');
  const [mm,dd,yy] = d.split('/');
  return `20${yy}-${mm}-${dd}T${t}:00`;
}
function saveT4(batches){
  localStorage.setItem(T4_KEY, JSON.stringify({batches, confirmedAt: new Date().toISOString()}));
}
function loadT4(){
  try{
    const raw = localStorage.getItem(T4_KEY);
    if(!raw) return null;
    const parsed = JSON.parse(raw);
    if(!parsed || !Array.isArray(parsed.batches)) return null;
    return parsed;
  }catch(_){ return null; }
}
