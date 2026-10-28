/* Wspólny widok drabinki direct elimination (panel organizatora i telefon zawodnika).
 *
 * Układ klasycznej tabeli: jedna kolumna na etap, walka następnego etapu stoi pośrodku dwóch walk, z których wynika,
 * a strzałki (SVG) pokazują, do którego miejsca w następnej walce trafi zwycięzca.
 * Na górze jest pasek etapów: wybranie etapu chowa wcześniejsze etapy. Tabela skaluje się do liczby widocznych walk
 * (im więcej walk w pierwszym widocznym etapie, tym mniejsza czcionka i karty).
 *
 * BracketView.render(container, bracket, ctx)
 *   bracket: { size, count, seeds, rounds: [[bout]], third, repasaze: [{ places, bouts }] }   bout: { id, a, b, sa, sb, bye, winner, ref }
 *   ctx: {
 *     name(id)            -> tekst do wyświetlenia
 *     me                  -> id zawodnika wyróżnionego (opcjonalnie)
 *     highlight           -> id walki wyróżnionej stałą ramką (opcjonalnie)
 *     editable            -> true: pola wyniku i wybór sędziego (panel organizatora)
 *     fit                 -> true: dopasuj skalę do szerokości kontenera i pokaż przyciski powiększania (telefon)
 *     threshold           -> maksymalna liczba trafień (15)
 *     onScore(id, aInput, bInput)
 *     onReferee(id, value)
 *     refereeOptions(bout) -> [{ id, label }]
 *   }
 */
(function () {
  'use strict';

  var CSS = [
    '.de-stages{display:flex;gap:6px;overflow-x:auto;padding:2px 0 10px;align-items:center;}',
    '.de-stages .de-stage-label{color:var(--muted);font-size:.8rem;white-space:nowrap;margin-right:2px;}',
    '.de-stages button{width:auto;flex:0 0 auto;padding:4px 10px;font:inherit;font-size:.82rem;border-radius:999px;' +
      'border:1px solid var(--border);background:transparent;color:var(--text);cursor:pointer;white-space:nowrap;}',
    '.de-stages button.active{background:var(--accent);border-color:var(--accent);color:#fff;}',
    '.de-stages .de-zoom{margin-left:auto;display:flex;gap:6px;flex:0 0 auto;}',
    '.de-stages .de-zoom button{min-width:2.2em;padding:4px 8px;}',
    '.de-scroll{overflow-x:auto;padding-bottom:8px;}',
    '.de-grid{position:relative;display:grid;width:max-content;}',
    '.de-head{font-weight:700;font-size:1.05em;align-self:center;}',
    '.de-slot{display:flex;align-items:center;min-width:0;}',
    '.de-bout{width:100%;border:1px solid var(--border);border-radius:.6em;background:var(--panel);position:relative;z-index:1;}',
    '.de-bout .de-title{font-size:.78em;color:var(--muted);padding:.2em .6em 0;}',
    '.de-row{display:flex;align-items:center;justify-content:space-between;gap:.5em;padding:.25em .6em;}',
    '.de-row+.de-row{border-top:1px solid var(--border);}',
    '.de-row .de-name{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}',
    '.de-row .de-seed{color:var(--muted);font-size:.85em;min-width:2em;}',
    '.de-row .de-score{min-width:1.7em;text-align:center;font-variant-numeric:tabular-nums;}',
    '.de-row.win{font-weight:700;background:var(--win-bg,var(--ok-bg));}',
    '.de-row.me .de-name{text-decoration:underline;text-underline-offset:.15em;}',
    '.de-row.empty-slot .de-name{color:var(--muted);font-style:italic;font-weight:400;}',
    '.de-row input{box-sizing:border-box;width:2.8em;min-width:0;padding:.2em .1em;text-align:center;font-size:1em;line-height:1.2;}',
    '.de-ref{display:flex;align-items:center;gap:.5em;padding:.2em .6em .35em;font-size:.85em;color:var(--muted);border-top:1px solid var(--border);}',
    '.de-ref select{flex:1 1 auto;min-width:0;max-width:11em;font:inherit;font-size:1em;padding:.1em .25em;}',
    '.de-ref .de-ref-name{color:var(--text);}',
    '.de-bout.de-next{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent);}',
    '.de-bout.de-flash{animation:de-flash 1s ease-in-out 3;}',
    '@keyframes de-flash{0%,100%{box-shadow:0 0 0 1px var(--accent);}50%{box-shadow:0 0 0 7px var(--accent);}}',
    '.de-rep{margin-top:18px;}',
    '.de-rep h3{margin:0 0 8px;font-size:1em;}',
    '.de-rep-grid{display:flex;flex-wrap:wrap;gap:.9em;align-items:flex-start;}',
    '.de-rep-card{flex:0 0 auto;}',
    '.de-lines{position:absolute;left:0;top:0;pointer-events:none;z-index:0;overflow:visible;}',
    '.de-lines path{fill:none;stroke:var(--muted);stroke-width:1.5;opacity:.55;}',
    '.de-lines path.won{stroke:var(--accent);stroke-width:2.5;opacity:1;}',
    '.de-lines marker path{fill:var(--muted);stroke:none;opacity:.8;}',
    '.de-lines marker.won path{fill:var(--accent);opacity:1;}'
  ].join('\n');
  var style = document.createElement('style');
  style.textContent = CSS;
  document.head.appendChild(style);

  var BASE_FONT_PX = 13;
  var BASE_COL_PX = 212;
  var BASE_GAP_PX = 44;
  var BASE_ROW_PX = 96;
  var BASE_ROW_EDIT_PX = 128;

  // Skala zależy od liczby walk w pierwszym widocznym etapie.
  function scaleFor(bouts) {
    if (bouts >= 32) return 0.66;
    if (bouts >= 16) return 0.76;
    if (bouts >= 8) return 0.88;
    return 1;
  }

  function roundTitle(bracket, index) {
    var inRound = bracket.size / Math.pow(2, index);
    if (index === 0 && bracket.count < bracket.size) return 'Dobijaki (tabela ' + bracket.size + ')';
    if (inRound === 2) return 'Finał';
    if (inRound === 4) return 'Półfinały';
    if (inRound === 8) return 'Ćwierćfinały';
    return 'Tabela ' + inRound;
  }

  function seedOf(bracket, id) {
    var i = bracket.seeds.indexOf(id);
    return i === -1 ? '' : '#' + (i + 1);
  }

  // Numery walk w kolejności rund (bez wolnych losów); walka o 3. miejsce, potem repasaże.
  // Kolejność musi być taka sama jak na serwerze (server.py, _numbered_bouts).
  function numbering(bracket) {
    var n = 0;
    var byId = {};
    var rounds = bracket.rounds.map(function (round) {
      return round.map(function (b) { if (b.bye) return null; byId[b.id] = ++n; return n; });
    });
    var third = null;
    if (bracket.third) { third = ++n; byId[bracket.third.id] = n; }
    var rep = (bracket.repasaze || []).map(function (grp) {
      return grp.bouts.map(function (b) { byId[b.id] = ++n; return n; });
    });
    return { rounds: rounds, third: third, rep: rep, byId: byId };
  }

  function buildBout(bracket, b, title, hints, ctx) {
    var card = document.createElement('div');
    card.className = 'de-bout' + (ctx.highlight && ctx.highlight === b.id ? ' de-next' : '');
    card.setAttribute('data-bout', b.id);
    var head = document.createElement('div');
    head.className = 'de-title';
    head.textContent = title;
    card.appendChild(head);
    var inputs = [];
    var rows = {};
    ['a', 'b'].forEach(function (side) {
      var id = b[side];
      var row = document.createElement('div');
      row.className = 'de-row' + (b.winner && b.winner === id ? ' win' : '') + (!id ? ' empty-slot' : '') +
        (ctx.me && id === ctx.me ? ' me' : '');
      var seed = document.createElement('span');
      seed.className = 'de-seed';
      seed.textContent = id ? seedOf(bracket, id) : '';
      var name = document.createElement('span');
      name.className = 'de-name';
      name.textContent = id ? ctx.name(id) : (b.bye ? 'wolny los' : (hints[side] || '—'));
      if (id) name.title = ctx.name(id);
      row.appendChild(seed);
      row.appendChild(name);
      if (!b.bye) {
        var value = side === 'a' ? b.sa : b.sb;
        if (ctx.editable) {
          var input = document.createElement('input');
          input.type = 'text';                 // zwykłe pole (bez strzałek góra/dół), żeby cyfry nie były ucinane
          input.inputMode = 'numeric';
          input.pattern = '[0-9]*';
          input.maxLength = String(ctx.threshold).length;
          input.autocomplete = 'off';
          input.disabled = !(b.a && b.b);
          input.value = value === null ? '' : String(value);
          input.setAttribute('aria-label', 'Trafienia: ' + (id ? ctx.name(id) : ''));
          inputs.push(input);
          row.appendChild(input);
        } else {
          var score = document.createElement('span');
          score.className = 'de-score';
          score.textContent = value === null ? '' : String(value);
          row.appendChild(score);
        }
      }
      card.appendChild(row);
      rows[side] = row;
    });

    if (!b.bye) {
      var refRow = document.createElement('div');
      refRow.className = 'de-ref';
      var label = document.createElement('span');
      label.textContent = 'Sędzia';
      refRow.appendChild(label);
      if (ctx.editable) {
        var select = document.createElement('select');
        select.setAttribute('aria-label', 'Sędzia walki ' + title);
        var none = document.createElement('option');
        none.value = '';
        none.textContent = '— brak —';
        select.appendChild(none);
        ctx.refereeOptions(b).forEach(function (o) {
          var option = document.createElement('option');
          option.value = o.id;
          option.textContent = o.label;
          select.appendChild(option);
        });
        select.value = b.ref || '';
        select.addEventListener('change', function () { ctx.onReferee(b.id, select.value); });
        refRow.appendChild(select);
        card.appendChild(refRow);
      } else if (b.ref) {
        var who = document.createElement('span');
        who.className = 'de-ref-name';
        who.textContent = ctx.name(b.ref);
        refRow.appendChild(who);
        card.appendChild(refRow);
      }
    }

    if (inputs.length === 2) {
      inputs.forEach(function (input) {
        input.addEventListener('change', function () { ctx.onScore(b.id, inputs[0], inputs[1]); });
      });
    }
    card._rows = rows;
    return card;
  }

  function drawLines(grid, cards) {
    var NS = 'http://www.w3.org/2000/svg';
    var svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('class', 'de-lines');
    svg.setAttribute('width', String(grid.scrollWidth));
    svg.setAttribute('height', String(grid.scrollHeight));
    var defs = document.createElementNS(NS, 'defs');
    ['', 'won'].forEach(function (kind) {
      var marker = document.createElementNS(NS, 'marker');
      marker.setAttribute('id', 'de-arrow' + kind);
      marker.setAttribute('class', kind);
      marker.setAttribute('viewBox', '0 0 10 10');
      marker.setAttribute('refX', '9');
      marker.setAttribute('refY', '5');
      marker.setAttribute('markerWidth', '7');
      marker.setAttribute('markerHeight', '7');
      marker.setAttribute('orient', 'auto');
      var tip = document.createElementNS(NS, 'path');
      tip.setAttribute('d', 'M0,0 L10,5 L0,10 z');
      marker.appendChild(tip);
      defs.appendChild(marker);
    });
    svg.appendChild(defs);

    var box = grid.getBoundingClientRect();
    function rel(el) {
      var r = el.getBoundingClientRect();
      return { left: r.left - box.left, right: r.right - box.left, mid: r.top - box.top + r.height / 2 };
    }
    for (var r = 0; r < cards.length - 1; r++) {
      cards[r].forEach(function (card, i) {
        var target = cards[r + 1][i >> 1];
        var from = rel(card);
        var to = rel(target._rows[i % 2 === 0 ? 'a' : 'b']);
        var mid = from.right + (to.left - from.right) / 2;
        var path = document.createElementNS(NS, 'path');
        var won = !!card._winner;
        path.setAttribute('d', 'M' + from.right + ',' + from.mid + ' H' + mid + ' V' + to.mid + ' H' + (to.left - 1));
        path.setAttribute('marker-end', 'url(#de-arrow' + (won ? 'won' : '') + ')');
        if (won) path.setAttribute('class', 'won');
        svg.appendChild(path);
      });
    }
    grid.appendChild(svg);
  }

  function render(container, bracket, ctx) {
    var state = container._de || (container._de = { from: 0 });
    var key = bracket.size + ':' + bracket.count;
    if (state.key !== key) { state.key = key; state.from = 0; state.zoom = 1; }   // nowa drabinka: wszystkie etapy
    state.bracket = bracket;
    state.ctx = ctx;
    var rounds = bracket.rounds;
    if (state.from < 0 || state.from > rounds.length - 1) state.from = 0;
    var from = state.from;

    var scrollEl = container.querySelector('.de-scroll');
    var previousScroll = scrollEl ? scrollEl.scrollLeft : 0;
    // zachowaj wysokość na czas przebudowy, żeby strona nie skakała (przewijanie)
    var keepHeight = container.offsetHeight;
    if (keepHeight > 0) container.style.minHeight = keepHeight + 'px';
    container.textContent = '';

    // pasek etapów: wybór pierwszego widocznego etapu (wcześniejsze są schowane)
    var bar = document.createElement('div');
    bar.className = 'de-stages';
    var barLabel = document.createElement('span');
    barLabel.className = 'de-stage-label';
    barLabel.textContent = 'Od etapu:';
    bar.appendChild(barLabel);
    rounds.forEach(function (round, r) {
      var chip = document.createElement('button');
      chip.type = 'button';
      chip.textContent = roundTitle(bracket, r);
      if (r === from) chip.className = 'active';
      chip.addEventListener('click', function () {
        state.from = r;
        render(container, state.bracket, state.ctx);
      });
      bar.appendChild(chip);
    });
    if (ctx.fit) {
      var zoom = document.createElement('span');
      zoom.className = 'de-zoom';
      [['−', 'Pomniejsz', 1 / 1.2], ['Dopasuj', 'Dopasuj do ekranu', null], ['+', 'Powiększ', 1.2]].forEach(function (z) {
        var b = document.createElement('button');
        b.type = 'button';
        b.textContent = z[0];
        b.setAttribute('aria-label', z[1]);
        b.addEventListener('click', function () {
          state.zoom = z[2] === null ? 1 : Math.max(0.5, Math.min(2.5, (state.zoom || 1) * z[2]));
          render(container, state.bracket, state.ctx);
        });
        zoom.appendChild(b);
      });
      bar.appendChild(zoom);
    }
    container.appendChild(bar);

    var numbers = numbering(bracket);
    var visible = rounds.slice(from);
    var base = visible[0].length;
    var extra = bracket.third ? 1 : 0;
    var scale = scaleFor(base);
    if (ctx.fit) {
      var cols = visible.length;
      var natural = cols * BASE_COL_PX + (cols - 1) * BASE_GAP_PX;
      var avail = container.clientWidth || (window.innerWidth - 32);
      scale = Math.max(0.6, Math.min(scale, avail / natural));   // nie mniej niż 60% (czytelność), reszta przewijana
      scale = Math.max(0.4, Math.min(1.6, scale * (state.zoom || 1)));
    }
    var rowPx = Math.round((ctx.editable ? BASE_ROW_EDIT_PX : BASE_ROW_PX) * scale);

    var scroll = document.createElement('div');
    scroll.className = 'de-scroll';
    var grid = document.createElement('div');
    grid.className = 'de-grid';
    grid.style.fontSize = (BASE_FONT_PX * scale).toFixed(2) + 'px';
    grid.style.columnGap = Math.round(BASE_GAP_PX * scale) + 'px';
    grid.style.gridTemplateColumns = 'repeat(' + visible.length + ', ' + Math.round(BASE_COL_PX * scale) + 'px)';
    grid.style.gridTemplateRows = Math.round(32 * scale) + 'px repeat(' + (base + extra) + ', ' + rowPx + 'px)';

    var cards = [];
    visible.forEach(function (round, v) {
      var r = from + v;
      var head = document.createElement('div');
      head.className = 'de-head';
      head.style.gridColumn = String(v + 1);
      head.style.gridRow = '1';
      head.textContent = roundTitle(bracket, r);
      grid.appendChild(head);

      var span = Math.pow(2, v);
      cards.push(round.map(function (b, i) {
        var hints = {};
        if (r > 0) {
          ['a', 'b'].forEach(function (side, k) {
            var feeder = numbers.rounds[r - 1][2 * i + k];
            if (feeder) hints[side] = 'Zwycięzca walki ' + feeder;
          });
        }
        var slot = document.createElement('div');
        slot.className = 'de-slot';
        slot.style.gridColumn = String(v + 1);
        slot.style.gridRow = (2 + i * span) + ' / span ' + span;
        var card = buildBout(bracket, b, numbers.rounds[r][i] ? 'Walka ' + numbers.rounds[r][i] : '', hints, ctx);
        card._winner = !!b.winner;
        slot.appendChild(card);
        grid.appendChild(slot);
        return card;
      }));
    });
    if (bracket.third) {
      var semis = numbers.rounds[rounds.length - 2];
      var slot3 = document.createElement('div');
      slot3.className = 'de-slot';
      slot3.style.gridColumn = String(visible.length);
      slot3.style.gridRow = String(2 + base);
      slot3.appendChild(buildBout(bracket, bracket.third, 'Walka o 3. miejsce (walka ' + numbers.third + ')', {
        a: 'Przegrany walki ' + semis[0], b: 'Przegrany walki ' + semis[1]
      }, ctx));
      grid.appendChild(slot3);
    }
    scroll.appendChild(grid);
    container.appendChild(scroll);
    scroll.scrollLeft = previousScroll;

    // repasaże: walki o miejsca (przegrani rundy grają między sobą klasyfikację)
    (bracket.repasaze || []).forEach(function (grp, gi) {
      var section = document.createElement('div');
      section.className = 'de-rep';
      section.style.fontSize = (BASE_FONT_PX * scale).toFixed(2) + 'px';
      var title = document.createElement('h3');
      title.textContent = 'Repasaże: miejsca ' + grp.places[0] + '–' + grp.places[1];
      section.appendChild(title);
      var list = document.createElement('div');
      list.className = 'de-rep-grid';
      grp.bouts.forEach(function (b, i) {
        var hints = {};
        ['a', 'b'].forEach(function (side) {
          var spec = b.src[side];
          var no = numbers.byId[spec.bout];
          hints[side] = (spec.t === 'winner' ? 'Zwycięzca walki ' : 'Przegrany walki ') + no;
        });
        var wrap = document.createElement('div');
        wrap.className = 'de-rep-card';
        wrap.style.width = Math.round(BASE_COL_PX * scale) + 'px';
        wrap.appendChild(buildBout(bracket, b, 'Walka ' + numbers.rep[gi][i] + ' · ' + b.title, hints, ctx));
        list.appendChild(wrap);
      });
      section.appendChild(list);
      container.appendChild(section);
    });
    requestAnimationFrame(function () {
      if (grid.isConnected && grid.offsetWidth > 0) drawLines(grid, cards);
      container.style.minHeight = '';
    });
  }

  // Przewija do walki (także poziomo w drabince) i na chwilę ją podświetla.
  // Jeśli jej etap jest schowany, najpierw pokazuje wszystkie etapy.
  function focus(container, boutId) {
    var card = container.querySelector('[data-bout="' + boutId + '"]');
    if (!card && container._de && container._de.from > 0) {
      container._de.from = 0;
      render(container, container._de.bracket, container._de.ctx);
      card = container.querySelector('[data-bout="' + boutId + '"]');
    }
    if (!card) return false;
    card.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'center' });
    card.classList.remove('de-flash');
    void card.offsetWidth;
    card.classList.add('de-flash');
    setTimeout(function () { card.classList.remove('de-flash'); }, 3200);
    return true;
  }

  // Ponowne narysowanie z ostatnimi danymi (np. po obrocie telefonu, gdy zmienia się szerokość).
  function refresh(container) {
    if (container._de && container._de.bracket) render(container, container._de.bracket, container._de.ctx);
  }

  window.BracketView = { render: render, refresh: refresh, focus: focus, roundTitle: roundTitle, numbering: numbering };
})();
