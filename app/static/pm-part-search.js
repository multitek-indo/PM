/* Multitek PM v0.4.2 - directly selectable sparepart search for stock movements.
 * The original Django select remains the only submitted "part" value.
 * If JavaScript is unavailable, the original required select remains usable.
 */
(function () {
  'use strict';
  var container = document.querySelector('[data-pm-part-picker]');
  if (!container) return;

  var query = container.querySelector('#inv-part-query');
  var status = container.querySelector('#inv-part-results');
  var choices = container.querySelector('#inv-part-choices');
  var picked = container.querySelector('#inv-part-picked');
  var select = container.querySelector('select[name="part"]');
  if (!query || !status || !choices || !picked || !select || !select.form) return;

  var limit = 40;
  var parts = Array.from(select.options).filter(function (option) {
    return option.value !== '';
  }).map(function (option) {
    return {
      value: option.value,
      label: option.textContent.trim(),
      search: option.textContent.toLocaleLowerCase('id')
    };
  });
  if (!parts.length) return;

  var originalSelection = parts.find(function (part) { return part.value === select.value; });
  var currentMatches = [];
  var originalRequired = select.required;

  function showChoices(visible) {
    choices.hidden = !visible;
    query.setAttribute('aria-expanded', visible ? 'true' : 'false');
  }

  function showSelection(part) {
    picked.hidden = !part;
    picked.textContent = part ? 'Terpilih: ' + part.label : '';
  }

  function choose(part) {
    select.value = part.value; // Preserve Django's existing ModelChoiceField ID.
    query.value = part.label;
    query.setCustomValidity('');
    showSelection(part);
    query.focus();
    showChoices(false);
    status.textContent = 'Sparepart dipilih. Anda dapat melanjutkan pengisian.';
  }

  function findMatches(text) {
    var terms = text.trim().toLocaleLowerCase('id').split(/\s+/).filter(Boolean);
    return terms.length ? parts.filter(function (part) {
      return terms.every(function (term) { return part.search.indexOf(term) !== -1; });
    }) : [];
  }

  function render() {
    currentMatches = findMatches(query.value);
    var fragment = document.createDocumentFragment();
    currentMatches.slice(0, limit).forEach(function (part) {
      var button = document.createElement('button');
      button.type = 'button';
      button.className = 'inv-part-option';
      button.textContent = part.label;
      button.setAttribute('aria-label', 'Pilih ' + part.label);
      button.addEventListener('click', function () { choose(part); });
      button.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
          event.preventDefault(); showChoices(false); query.focus();
        } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
          event.preventDefault();
          var buttons = Array.from(choices.querySelectorAll('button'));
          var index = buttons.indexOf(button);
          var next = buttons[index + (event.key === 'ArrowDown' ? 1 : -1)];
          if (next) next.focus(); else query.focus();
        }
      });
      fragment.appendChild(button);
    });
    choices.replaceChildren(fragment);
    if (!query.value.trim()) {
      status.textContent = 'Ketik kode atau nama sparepart, lalu pilih hasil pencarian.';
      showChoices(false);
    } else if (!currentMatches.length) {
      status.textContent = 'Tidak ada sparepart yang cocok. Coba kata lain.';
      showChoices(false);
    } else {
      status.textContent = currentMatches.length > limit
        ? 'Menampilkan ' + limit + ' dari ' + currentMatches.length + ' sparepart. Ketik lebih spesifik.'
        : currentMatches.length + ' sparepart ditemukan. Klik nama sparepart untuk memilih.';
      showChoices(true);
    }
  }

  // Do not enable the enhanced UI until its controls are ready.
  query.hidden = false;
  query.required = originalRequired;
  query.value = originalSelection ? originalSelection.label : '';
  status.hidden = false;
  showSelection(originalSelection || null);
  showChoices(false);
  if (!originalSelection) status.textContent = 'Ketik kode atau nama sparepart, lalu pilih hasil pencarian.';

  select.required = false; // Required validation is now on the visible input.
  select.tabIndex = -1;
  select.setAttribute('aria-hidden', 'true');
  var outerLabel = document.querySelector('label[for="' + select.id + '"]');
  if (outerLabel) outerLabel.htmlFor = query.id;
  container.classList.add('inv-part-enhanced');

  query.addEventListener('input', function () {
    select.value = ''; // Never use a stale selected part after editing the query.
    showSelection(null);
    query.setCustomValidity('');
    render();
  });
  query.addEventListener('focus', function () {
    if (query.value.trim()) render();
  });
  query.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') {
      showChoices(false);
    } else if (event.key === 'ArrowDown' && !choices.hidden) {
      var first = choices.querySelector('button');
      if (first) { event.preventDefault(); first.focus(); }
    } else if (event.key === 'Enter') {
      if (!choices.hidden && currentMatches.length === 1) {
        event.preventDefault(); choose(currentMatches[0]);
      } else if (!choices.hidden) {
        var firstResult = choices.querySelector('button');
        if (firstResult) { event.preventDefault(); firstResult.focus(); }
      } else if (!select.value) {
        event.preventDefault();
        query.setCustomValidity('Pilih sparepart dari hasil pencarian.');
        query.reportValidity();
      }
    }
  });
  document.addEventListener('click', function (event) {
    if (!container.contains(event.target)) showChoices(false);
  });
  select.form.addEventListener('submit', function (event) {
    if (!select.value) {
      event.preventDefault();
      query.setCustomValidity('Pilih sparepart dari hasil pencarian, bukan hanya mengetik namanya.');
      query.reportValidity();
      query.focus();
    }
  });
})();
