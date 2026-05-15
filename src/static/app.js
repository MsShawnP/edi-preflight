function switchMode(mode) {
    document.querySelectorAll('.mode-tab').forEach(function(t) {
        t.classList.remove('active');
    });
    document.querySelector('[data-mode="' + mode + '"]').classList.add('active');
    var panels = document.querySelectorAll('.mode-panel');
    panels.forEach(function(p) {
        if (p.id === 'mode-' + mode) {
            p.classList.remove('mode-panel-hidden');
        } else {
            p.classList.add('mode-panel-hidden');
        }
    });
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
