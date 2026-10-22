// House deck runtime: reveal configuration and depth-on-demand overlays.
(function () {
  Reveal.initialize({
    width: 1920,
    height: 1080,
    margin: 0,
    minScale: 0.05,
    maxScale: 4,
    center: false,
    hash: true,
    history: false,
    controls: false,
    progress: true,
    slideNumber: false,
    transition: 'none',
    backgroundTransition: 'none',
    pdfSeparateFragments: true,
    pdfMaxPagesPerSlide: 1,
    plugins: [RevealNotes],
  });

  var openDetail = null;

  function close() {
    if (!openDetail) return;
    openDetail.classList.remove('open');
    openDetail = null;
    Reveal.configure({ keyboard: true });
  }

  function open(section, k) {
    close();
    var d = section.querySelector(':scope > .slide.detail[data-detail="' + k + '"]');
    if (!d) return;
    d.classList.add('open');
    openDetail = d;
    Reveal.configure({ keyboard: false });
  }

  document.addEventListener('click', function (e) {
    var chip = e.target.closest('.chip[data-open]');
    if (chip) { open(chip.closest('section'), chip.getAttribute('data-open')); e.stopPropagation(); return; }
    if (e.target.closest('.slide.detail .close')) { close(); e.stopPropagation(); }
  }, true);

  document.addEventListener('keydown', function (e) {
    if (openDetail && (e.key === 'Escape' || e.key === 'Backspace')) { close(); e.preventDefault(); e.stopPropagation(); }
  }, true);

  Reveal.addKeyBinding({ keyCode: 68, key: 'D', description: 'Open this slide\'s first detail' }, function () {
    var s = Reveal.getCurrentSlide();
    if (s && s.querySelector(':scope > .slide.detail')) open(s, '0');
  });

  Reveal.on('slidechanged', close);

  // Hooks for the checker and for scripted capture.
  window.House = { open: open, close: close };
})();
