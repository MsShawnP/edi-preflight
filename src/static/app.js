function switchMode(mode) {
    document.querySelectorAll('.mode-tab').forEach(function(t) {
        t.classList.remove('active');
    });
    document.querySelector('[data-mode="' + mode + '"]').classList.add('active');
    document.getElementById('mode-inbound').style.display = mode === 'inbound' ? 'block' : 'none';
    document.getElementById('mode-outbound').style.display = mode === 'outbound' ? 'block' : 'none';
    document.getElementById('results').innerHTML = '';
}

function loadSample(docType, textareaId) {
    fetch('/sample/' + docType)
        .then(function(r) { return r.text(); })
        .then(function(text) {
            var ta = document.getElementById(textareaId);
            ta.value = text;
            ta.closest('form').querySelector('button[type="submit"]').click();
        });
}

document.querySelectorAll('.mode-tab').forEach(function(tab) {
    tab.addEventListener('click', function() {
        switchMode(this.dataset.mode);
    });
});

document.querySelectorAll('.try-sample').forEach(function(btn) {
    btn.addEventListener('click', function() {
        loadSample(this.dataset.docType, this.dataset.textareaId);
    });
});
