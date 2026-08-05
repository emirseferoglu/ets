/* =========================================================================
   Tasarruf Finansmanı Hesaplama Mantığı
   -------------------------------------------------------------------------
   Model (faizsiz / interest-free):
     - Aylık taksit  = (Finansman tutarı - Peşinat) / Vade
     - Organizasyon ücreti = Finansman tutarı * (oran / 100)   -> tek maliyet
     - Toplam ödenecek = (Finansman tutarı - Peşinat) + Organizasyon ücreti
     - Efektif maliyet oranı = Organizasyon ücreti / Finansman tutarı
     - Teslim (tahsis) ayı:
         * Çekilişsiz: birikim sözleşme tutarının %40'ına ulaşınca
                       -> ceil(vade * 0.40), en erken 6. ay (180 gün)
         * Çekilişli : garanti teslim ayı ~ vade * 0.66 (kura ile daha erken olabilir)
   ========================================================================= */

const TL = new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY', maximumFractionDigits: 0 });
const NUM = new Intl.NumberFormat('tr-TR');

// Karşılaştırma tablosu için temsilî firma oranları (organizasyon ücreti %)
const FIRMS = [
  { name: 'Eminevim',       ev: 8.0, araba: 7.0 },
  { name: 'Fuzul Ev',       ev: 7.5, araba: 6.5 },
  { name: 'Katılımevim',    ev: 8.5, araba: 7.5 },
  { name: 'İmece Tasarruf', ev: 6.5, araba: 6.0 },
  { name: 'Emlak Katılım',  ev: 5.5, araba: 5.0 },
];

const state = {
  product: 'ev',
  draw: 'cekilissiz',
  amount: 1500000,
  down: 0,
  term: 60,
  orgFee: 8,
};

/* ---------- helpers ---------- */
function parseNum(str) {
  const n = parseInt(String(str).replace(/[^\d]/g, ''), 10);
  return isNaN(n) ? 0 : n;
}
function fmtInput(el) { el.value = NUM.format(parseNum(el.value)); }

/* ---------- core calculation ---------- */
function calculate(amount, down, term, orgFeeRate, draw) {
  down = Math.min(down, amount);
  const financed = amount - down;
  const monthly = term > 0 ? financed / term : 0;
  const orgFee = amount * (orgFeeRate / 100);
  const total = financed + orgFee;
  const effective = amount > 0 ? orgFee / amount : 0;

  let delivery;
  if (draw === 'cekilissiz') {
    delivery = Math.max(6, Math.ceil(term * 0.40));   // %40 birikim, en erken 6. ay
  } else {
    delivery = Math.max(6, Math.round(term * 0.66));  // garanti teslim ayı (kura ile erkeni mümkün)
  }

  return { financed, monthly, orgFee, total, effective, delivery };
}

/* ---------- render ---------- */
function render() {
  const r = calculate(state.amount, state.down, state.term, state.orgFee, state.draw);

  document.getElementById('rMonthly').textContent = TL.format(Math.round(r.monthly));
  document.getElementById('rOrgFee').textContent  = TL.format(Math.round(r.orgFee));
  document.getElementById('rTotal').textContent   = TL.format(Math.round(r.total)); // toplam = financed + orgFee
  document.getElementById('rDelivery').textContent = r.delivery + '. ay';
  document.getElementById('rEffective').textContent = '%' + (r.effective * 100).toFixed(1);

  const note = state.draw === 'cekilissiz'
    ? `Çekilişsiz modelde birikiminiz sözleşme tutarının %40'ına ulaştığında (yaklaşık ${r.delivery}. ay), en erken 180. günden sonra teslim yapılır.`
    : `Çekilişli modelde her ay kura çekilir; adınız çıkarsa daha erken teslim alırsınız. Garanti teslim ayı yaklaşık ${r.delivery}. aydır.`;
  document.getElementById('rNote').textContent = note;

  renderCompare();
}

function renderCompare() {
  const body = document.getElementById('compareBody');
  const rows = FIRMS.map(f => {
    const rate = f[state.product];
    const c = calculate(state.amount, state.down, state.term, rate, state.draw);
    return { name: f.name, rate, orgFee: c.orgFee, monthly: c.monthly, total: c.total };
  }).sort((a, b) => a.total - b.total);

  const best = rows[0];
  body.innerHTML = rows.map(row => `
    <tr class="${row === best ? 'best-row' : ''}">
      <td>${row.name}${row === best ? '<span class="best-tag">En Uygun</span>' : ''}</td>
      <td>%${row.rate.toFixed(1)}</td>
      <td>${TL.format(Math.round(row.orgFee))}</td>
      <td>${TL.format(Math.round(row.monthly))}</td>
      <td>${TL.format(Math.round(row.total))}</td>
    </tr>`).join('');
}

/* ---------- wiring ---------- */
function initSegmented(id, key, onChange) {
  const grp = document.getElementById(id);
  grp.querySelectorAll('.seg').forEach(btn => {
    btn.addEventListener('click', () => {
      grp.querySelectorAll('.seg').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state[key] = btn.dataset.value;
      if (onChange) onChange();
      render();
    });
  });
}

document.addEventListener('DOMContentLoaded', () => {
  const amount = document.getElementById('amount');
  const amountRange = document.getElementById('amountRange');
  const down = document.getElementById('downPayment');
  const term = document.getElementById('term');
  const termOut = document.getElementById('termOut');
  const orgFee = document.getElementById('orgFee');
  const orgFeeOut = document.getElementById('orgFeeOut');
  const drawHint = document.getElementById('drawHint');

  initSegmented('productType', 'product');
  initSegmented('drawType', 'draw', () => {
    drawHint.textContent = state.draw === 'cekilissiz'
      ? "Birikiminiz sözleşmenin %40'ına ulaştığında teslim alırsınız."
      : "Her ay kura çekilir; adınız çıkarsa erken teslim alırsınız.";
  });

  amount.addEventListener('input', () => {
    fmtInput(amount);
    state.amount = parseNum(amount.value);
    amountRange.value = Math.min(Math.max(state.amount, +amountRange.min), +amountRange.max);
    render();
  });
  amountRange.addEventListener('input', () => {
    state.amount = +amountRange.value;
    amount.value = NUM.format(state.amount);
    render();
  });
  down.addEventListener('input', () => {
    fmtInput(down);
    state.down = parseNum(down.value);
    render();
  });
  term.addEventListener('input', () => {
    state.term = +term.value;
    termOut.textContent = state.term + ' ay';
    render();
  });
  orgFee.addEventListener('input', () => {
    state.orgFee = +orgFee.value;
    orgFeeOut.textContent = '%' + state.orgFee;
    render();
  });

  render();
});
