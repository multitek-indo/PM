/* v0.4.1: client-side search for active parts on stock movements only.
 * No extra API, no new submitted fields, and native select stays usable without JS.
 */
(function () {
  'use strict';
  var container = document.querySelector('[data-pm-part-picker]');
  if (!container) return;
  var query = container.querySelector('#inv-part-query');
  var status = container.querySelector('#inv-part-results');
  var select = container.querySelector('select[name="part"]');
  if (!query || !status || !select) return;

  var limit = 40;
  var original = Array.from(select.options).filter(function (o) { return o.value !== ''; }).map(function (o) {
    return { value: o.value, label: o.textContent.trim(), search: o.textContent.toLocaleLowerCase('id') };
  });
  var previous = select.value;
  var previousItem = original.find(function (o) { return o.value === previous; });

  function refresh(searchText, selectedValue) {
    var terms = searchText.toLocaleLowerCase('id').trim().split(/\s+/).filter(Boolean);
    var matching = terms.length ? original.filter(function (part) {
      return terms.every(function (term) { return part.search.indexOf(term) !== -1; });
    }) : original;
    var shown = matching.slice(0, limit);
    var frag = document.createDocumentFragment();
    var empty = document.createElement('option');
    empty.value = '';
    empty.textContent = matching.length === 0 ? '-- Tidak ditemukan --' : '-- Pilih sparepart --';
    frag.appendChild(empty);
    shown.forEach(function (part) {
      var option = document.createElement('option');
      option.value = part.value;
      option.textContent = part.label;
      frag.appendChild(option);
    });
    select.replaceChildren(frag);
    select.value = selectedValue && shown.some(function (p) { return p.value === selectedValue; }) ? selectedValue : '';
    if (matching.length === 0) {
      status.textContent = 'Tidak ada sparepart yang cocok. Coba kode atau nama lain.';
    } else if (matching.length > limit) {
      status.textContent = 'Menampilkan ' + limit + ' dari ' + matching.length + ' sparepart. Ketik lebih spesifik.';
    } else {
      status.textContent = matching.length + ' sparepart ditemukan. Pilih dari daftar di bawah.';
    }
  }

  if (previousItem) query.value = previousItem.label;
  query.hidden = false;
  status.hidden = false;
  refresh(query.value, previousItem ? previousItem.value : '');
  query.addEventListener('input', function () { refresh(query.value, ''); });
  query.addEventListener('keydown', function (event) {
    if (event.key === 'ArrowDown') { event.preventDefault(); select.focus(); }
  });
  select.addEventListener('change', function () {
    var chosen = original.find(function (part) { return part.value === select.value; });
    if (chosen) query.value = chosen.label;
  });
})();
