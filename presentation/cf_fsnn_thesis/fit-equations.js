<script>
// Auto-fit: shrink the content of every .eq / .eq.math panel so a wide equation
// or table never spills outside its box. KaTeX renders in em, so reducing the
// wrapper font-size shrinks the formula AND its layout width exactly by the
// same ratio — no transform artifacts, layout stays correct. Runs on load, on
// every slide change, and on resize.
(function () {
  function widest(inner) {
    var need = inner.scrollWidth;
    inner.querySelectorAll('.katex, table').forEach(function (el) {
      if (el.offsetWidth > need) need = el.offsetWidth;
      if (el.scrollWidth > need) need = el.scrollWidth;
    });
    return need;
  }
  function fit() {
    document.querySelectorAll('.reveal .eq').forEach(function (box) {
      var inner = box.querySelector(':scope > .eq-scale');
      if (!inner) {
        inner = document.createElement('div');
        inner.className = 'eq-scale';
        inner.style.display = 'inline-block';
        while (box.firstChild) inner.appendChild(box.firstChild);
        box.appendChild(inner);
        box.style.textAlign = 'center';
      }
      inner.style.fontSize = '';                    // reset to inherited size
      var avail = box.clientWidth - 14;             // margin for padding/border on both sides
      var need = widest(inner);
      if (need > avail && avail > 0) {
        var base = parseFloat(getComputedStyle(inner).fontSize) || 16;
        inner.style.fontSize = (base * avail / need).toFixed(2) + 'px';
        // one corrective pass in case reflow shifts the widest element
        var need2 = widest(inner);
        if (need2 > avail) inner.style.fontSize = (base * avail / need * avail / need2).toFixed(2) + 'px';
      }
    });
  }
  function schedule() { requestAnimationFrame(function () { setTimeout(fit, 30); }); }
  if (window.Reveal && Reveal.on) {
    Reveal.on('ready', schedule);
    Reveal.on('slidechanged', schedule);
    Reveal.on('resize', schedule);
  }
  window.addEventListener('load', function () { setTimeout(fit, 350); });
})();
</script>
