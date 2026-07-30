function switchMode(mode) {
    document.querySelectorAll('.mode-tab').forEach(function(t) {
        var isActive = t.dataset.mode === mode;
        t.classList.toggle('active', isActive);
        t.setAttribute('aria-selected', isActive ? 'true' : 'false');
    });
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
        .then(function(r) {
            if (!r.ok) {
                throw new Error('Sample request failed: ' + r.status);
            }
            return r.text();
        })
        .then(function(text) {
            var ta = document.getElementById(textareaId);
            ta.value = text;
            ta.closest('form').querySelector('button[type="submit"]').click();
        })
        .catch(function() {
            // Never auto-submit a failed fetch (a 404 body would parse as
            // garbage). Show a static message instead — no user data, so
            // assigning innerHTML here is safe.
            document.getElementById('results').innerHTML =
                '<div class="error-panel">' +
                '<h2>Could not load sample</h2>' +
                '<p class="error-message">The sample could not be loaded. ' +
                'Please try again in a moment.</p></div>';
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

// Move focus to the first heading of a freshly swapped result so screen-reader
// users are taken to the new content instead of being left on the submit
// button with no announcement. The results container is also aria-live.
document.getElementById('results').addEventListener('htmx:afterSwap', function() {
    var heading = this.querySelector('h2, h3');
    if (heading) {
        heading.setAttribute('tabindex', '-1');
        heading.focus();
    }
});
