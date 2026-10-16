document.addEventListener('DOMContentLoaded', function () {
  'use strict';
  const search = document.querySelector('[data-admin-search]');
  if (search) search.addEventListener('input', function () {
    const q = this.value.trim().toLocaleLowerCase('id');
    document.querySelectorAll('[data-admin-card]').forEach(card => {card.hidden = !card.textContent.toLocaleLowerCase('id').includes(q);});
  });
  const upload = document.querySelector('.import-form input[type=file]');
  const feedback = document.querySelector('[data-file-feedback]');
  if (upload && feedback) upload.addEventListener('change', function () {
    const f = this.files[0]; feedback.textContent = f ? f.name + ' | ' + (f.size/1024/1024).toFixed(2) + ' MiB' : 'Belum ada file dipilih.';
  });
});
