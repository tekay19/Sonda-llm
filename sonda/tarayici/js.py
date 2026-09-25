"""Sayfaya verilen JavaScript: öğeleri numaralandırma ve açıklama. Açıklama fonksiyonu her çağrıda
yeniden verilir (window'a konmaz): sayfa onu değiştirip öğeleri farklı gösteremesin."""



ACIKLA = r"""(e) => {
  const form = e.form || e.closest('form');
  const yazi = s => (s || '').replace(/\s+/g, ' ').trim();
  const girdi = ['INPUT', 'TEXTAREA', 'SELECT'].includes(e.tagName);
  let metin = '';
  if (e.labels && e.labels.length) metin = e.labels[0].innerText;
  if (!metin && !girdi) metin = e.innerText;
  if (!metin && e.querySelector) { const img = e.querySelector('img[alt]'); if (img) metin = img.alt; }
  const r = e.getBoundingClientRect();
  const d = {
    no: Number(e.getAttribute('data-sonda-id')) || 0,
    etiket: e.tagName.toLowerCase(), rol: e.getAttribute('role') || '',
    tip: (e.getAttribute('type') || '').toLowerCase(), ad: e.getAttribute('name') || '', kimlik: e.id || '',
    otomatik: (e.getAttribute('autocomplete') || '').toLowerCase(), yer: e.getAttribute('placeholder') || '',
    aria: e.getAttribute('aria-label') || '', baslik: e.getAttribute('title') || '',
    metin: yazi(metin).slice(0, 120),
    deger: (girdi ? String(e.value || '') : '').slice(0, 80),
    uzunluk: girdi ? String(e.value || '').length : 0,
    href: e.tagName === 'A' ? (e.href || '') : '',
    form: form ? [...document.forms].indexOf(form) : -1,
    form_eylem: form ? (form.getAttribute('action') || '') : '',
    ekranda: r.bottom > 0 && r.top < innerHeight,
  };
  if (e.tagName === 'SELECT') { d.secenekler = [...e.options].slice(0, 25).map(o => yazi(o.text)); d.deger = yazi(e.selectedOptions[0]?.text); }
  if (e.type === 'checkbox' || e.type === 'radio') d.secili = e.checked;
  // Gizli kutunun görünen etiketi (Upwork air3): tıklanınca kutu değişir; tipi ve durumu kutudan gelir
  const k = e.tagName === 'LABEL' ? e.control : null;
  if (k && (k.type === 'checkbox' || k.type === 'radio')) { d.tip = k.type; d.secili = k.checked; d.ad = k.name || ''; }
  return d;
}"""


BAK = "() => { const acikla = " + ACIKLA + r""";
  const SECICI = 'a[href], button, input:not([type=hidden]), select, textarea, summary, [role=button], [role=link], [role=tab], [role=checkbox], [role=radio], [role=option], [role=menuitem], [role=searchbox], [role=combobox], [contenteditable=""], [contenteditable=true], [onclick]';
  document.querySelectorAll('[data-sonda-id]').forEach(e => e.removeAttribute('data-sonda-id'));
  const gorunur = e => { const r = e.getBoundingClientRect(); if (r.width < 2 || r.height < 2) return false;
    const s = getComputedStyle(e); return s.visibility !== 'hidden' && s.display !== 'none' && Number(s.opacity) > 0.05; };
  const ogeler = []; let no = 0;
  for (let e of document.querySelectorAll(SECICI)) {
    if (e.disabled) continue;
    if (!gorunur(e)) {
      // Ekran okuyucu için gizlenmiş onay kutusu/radyo: görünen etiketi numaralanır
      const etiket = (e.type === 'checkbox' || e.type === 'radio') && ((e.labels && e.labels[0]) || e.closest('label'));
      if (!etiket || !gorunur(etiket) || etiket.hasAttribute('data-sonda-id')) continue;
      e = etiket;
    }
    e.setAttribute('data-sonda-id', ++no);
    ogeler.push(acikla(e));
  }
  // Sadece ekranda (ve hemen altında) görünen metin: kaydırınca model sayfanın devamını görür
  const parcalar = []; let uzunluk = 0;
  if (document.body) {
    const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const alt = innerHeight + 300;
    for (let n; (n = w.nextNode()) && uzunluk < 3000;) {
      const t = n.textContent.replace(/\s+/g, ' ').trim(); const el = n.parentElement;
      if (!t || !el || ['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE'].includes(el.tagName)) continue;
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.bottom < -50 || r.top > alt) continue;
      if (getComputedStyle(el).visibility === 'hidden') continue;
      parcalar.push(t); uzunluk += t.length + 1;
    }
  }
  const kaydirma = { y: Math.round(scrollY), yukseklik: document.documentElement.scrollHeight, ekran: innerHeight };
  return { url: location.href, baslik: document.title, ogeler, metin: parcalar.join(' ').slice(0, 3000), kaydirma };
}"""


ENGEL = """(e) => {
  e.scrollIntoView({ block: "center" });
  const r = e.getBoundingClientRect();
  const u = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
  if (!u || u === e || e.contains(u) || u.contains(e)) return null;
  const kap = u.closest("[role=dialog], [aria-modal=true], dialog") || u;
  return (kap.innerText || kap.getAttribute("aria-label") || kap.id || kap.tagName).replace(/\s+/g, " ").trim().slice(0, 120);
}"""

# Cloudflare bekleme ekranı başlıkları (onay kutusu henüz yüklenmemiş olabilir)
CAPTCHA_BASLIKLARI = ("just a moment", "bir dakika", "checking your browser", "attention required")
CAPTCHA_KUTULARI = ("#recaptcha-anchor", "#checkbox", "input[type=checkbox]", "[role=checkbox]")

