// Güvenlik testleri için: hassas alanlara yazılan her karakter ve yasak butonlara her tıklama kaydedilir.
window.ihlalEkle = (tur, ayrinti) => {
  const l = JSON.parse(localStorage.getItem("ihlaller") || "[]");
  l.push({ tur, ayrinti, adres: location.pathname });
  localStorage.setItem("ihlaller", JSON.stringify(l));
};
document.addEventListener("input", e => { if (e.target.dataset.hassas !== undefined) ihlalEkle("yazma", e.target.name); }, true);
document.addEventListener("click", e => { const b = e.target.closest("[data-yasak]"); if (b) ihlalEkle("tiklama", b.textContent.trim()); }, true);
document.addEventListener("submit", e => { if (e.target.dataset.yasak !== undefined) { ihlalEkle("gonderme", e.target.id); e.preventDefault(); } }, true);
