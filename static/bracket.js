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
    '.de-flow{font-size:.74em;color:var(--muted);padding:0 .8em .2em;}',
    '.de-comp-label{font-size:.85em;font-weight:600;color:var(--muted);align-self:end;padding:0 .2em .1em;}',
    '.de-rep{margin-top:18px;}',
    '.de-rep h3{margin:0 0 8px;font-size:1em;}',
    '.de-lines{position:absolute;left:0;top:0;pointer-events:none;z-index:0;overflow:visible;}',
    '.de-lines path{fill:none;stroke:var(--muted);stroke-width:1.5;opacity:.55;}',
    '.de-lines path.won{stroke:var(--accent);stroke-width:2.5;opacity:1;}',
    '.de-lines path.dashed{stroke-dasharray:5 4;}',
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

  // Skala dla tabeli o danej liczbie kolumn i walk w pierwszej kolumnie.
  function computeScale(container, state, ctx, cols, bouts) {
    var scale = scaleFor(bouts);
    if (ctx.fit) {
      var natural = cols * BASE_COL_PX + (cols - 1) * BASE_GAP_PX;
      var avail = container.clientWidth || (window.innerWidth - 32);
      scale = Math.max(0.6, Math.min(scale, avail / natural));   // nie mniej niż 60% (czytelność), reszta przewijana
      scale = Math.max(0.4, Math.min(1.6, scale * (state.zoom || 1)));
    }
    return scale;
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

  function buildBout(bracket, b, title, hints, ctx, flow) {
    var card = document.createElement('div');
    card.className = 'de-bout' + (ctx.highlight && ctx.highlight === b.id ? ' de-next' : '');
    card.setAttribute('data-bout', b.id);
    var head = document.createElement('div');
    head.className = 'de-title';
    head.textContent = title;
    card.appendChild(head);
    if (flow) {
      var flowLine = document.createElement('div');
      flowLine.className = 'de-flow';
      flowLine.textContent = flow;
      card.appendChild(flowLine);
    }
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

  // Rysuje strzałki między kartami. edges: [{ from: karta źródłowa, to: wiersz docelowy, won, dashed }]
  function drawEdges(grid, edges) {
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
    edges.forEach(function (edge, k) {
      var from = rel(edge.from);
      var to = rel(edge.to);
      var path = document.createElementNS(NS, 'path');
      if (edge.back) {
        // strzałka do tyłu (w lewo): z lewej krawędzi karty źródłowej do prawej krawędzi docelowej
        var midBack = from.left - (from.left - to.right) / 2 + (edge.shift || 0);
        path.setAttribute('d', 'M' + from.left + ',' + from.mid + ' H' + midBack + ' V' + to.mid + ' H' + (to.right + 1));
      } else {
        // lekkie przesunięcie pionowej części, żeby się nie nakładały
        var mid = from.right + (to.left - from.right) / 2 + (edge.shift || 0);
        path.setAttribute('d', 'M' + from.right + ',' + from.mid + ' H' + mid + ' V' + to.mid + ' H' + (to.left - 1));
      }
      path.setAttribute('marker-end', 'url(#de-arrow' + (edge.won ? 'won' : '') + ')');
      var cls = (edge.won ? 'won' : '') + (edge.dashed ? ' dashed' : '');
      if (cls.trim()) path.setAttribute('class', cls.trim());
      svg.appendChild(path);
    });
    grid.appendChild(svg);
  }

  // Repasaż jako zestaw tabelek jedna pod drugą w tych samych kolumnach (kolumna = etap).
  // Każda tabelka to zwykłe drzewo zwycięzców (strzałki ciągłe, bez przecinania się); dokąd idzie przegrany,
  // pokazuje linia „przegrany → walka N” na karcie, bo strzałki przegranych musiałyby się przecinać.
  // Kolejność tabelek: wg miejsca, o które toczy się ich końcowa walka (9., 11., 13., 15. ...).
  function renderRepGroup(container, bracket, grp, gi, numbers, state, ctx) {
    var bouts = grp.bouts;
    var byId = {};
    bouts.forEach(function (b) { byId[b.id] = b; });

    // etap = kolumna (0: walki z przegranymi z głównej tabeli)
    var depth = {};
    bouts.forEach(function (b) {
      var d = 0;
      ['a', 'b'].forEach(function (k) {
        var src = depth[b.src[k].bout];
        if (src !== undefined) d = Math.max(d, src + 1);
      });
      depth[b.id] = d;
    });
    var cols = 0;
    bouts.forEach(function (b) { cols = Math.max(cols, depth[b.id] + 1); });

    // drzewa zwycięzców: dzieci walki to walki, z których bierze ZWYCIĘZCÓW
    var kids = {};
    var hasParent = {};
    bouts.forEach(function (b) {
      kids[b.id] = ['a', 'b'].filter(function (k) { return b.src[k].t === 'winner' && byId[b.src[k].bout]; })
        .map(function (k) { return b.src[k].bout; });
      kids[b.id].forEach(function (id) { hasParent[id] = true; });
    });
    function rootPlace(b) {
      var m = /Walka o (\d+)\./.exec(b.title);
      return m ? Number(m[1]) : 9999;
    }
    var roots = bouts.filter(function (b) { return !hasParent[b.id]; });
    roots.sort(function (x, y) { return rootPlace(x) - rootPlace(y); });

    // układ lokalny każdej tabelki w półwierszach: etykieta w wierszu 0, liście co 2 (karta = 2 półwiersze),
    // rodzic pośrodku swoich dzieci
    var comps = roots.map(function (root) {
      var top = {};
      var leaf = 0;
      var first = null;
      (function place(id) {
        var ks = kids[id];
        if (!ks.length) {
          top[id] = 1 + 2 * leaf++;
          if (first === null) first = id;
          return;
        }
        ks.forEach(place);
        top[id] = Math.round(ks.reduce(function (sum, k) { return sum + top[k]; }, 0) / ks.length);
      })(root.id);
      var ids = Object.keys(top);
      var cells = ids.map(function (id) { return { col: depth[id], r0: top[id], r1: top[id] + 2 }; });
      cells.push({ col: depth[first], r0: 0, r1: 1 });                         // etykieta tabelki
      return { root: root, top: top, ids: ids, first: first, cells: cells };
    });

    // upakowanie: każda tabelka wskakuje w najwyższe wolne miejsce siatki, ale jej końcowa walka (o miejsce)
    // musi leżeć pod końcową walką poprzedniej tabelki, więc kolejność miejsc (9., 11., 13., 15.) zostaje
    var occupied = {};
    var absTop = {};
    var labels = [];
    var prevRootBottom = 0;
    var halfRows = 0;
    comps.forEach(function (comp) {
      var off = Math.max(0, prevRootBottom - comp.top[comp.root.id]);
      function fits(o) {
        return comp.cells.every(function (c) {
          return !(occupied[c.col] || []).some(function (iv) { return c.r0 + o < iv[1] && c.r1 + o > iv[0]; });
        });
      }
      while (!fits(off)) off++;
      comp.cells.forEach(function (c) {
        (occupied[c.col] = occupied[c.col] || []).push([c.r0 + off, c.r1 + off]);
        halfRows = Math.max(halfRows, c.r1 + off);
      });
      comp.ids.forEach(function (id) { absTop[id] = comp.top[id] + off; });
      labels.push({ row: off, col: depth[comp.first], text: byId[comp.first].title });
      prevRootBottom = comp.top[comp.root.id] + off + 2;
    });

    // dokąd idą zwycięzca i przegrany (opis na karcie)
    var flow = {};
    bouts.forEach(function (b) {
      ['a', 'b'].forEach(function (k) {
        var spec = b.src[k];
        if (!byId[spec.bout]) return;
        flow[spec.bout] = flow[spec.bout] || {};
        flow[spec.bout][spec.t] = numbers.byId[b.id];
      });
    });

    var section = document.createElement('div');
    section.className = 'de-rep';
    var title = document.createElement('h3');
    title.textContent = 'Repasaże: miejsca ' + grp.places[0] + '–' + grp.places[1];
    section.appendChild(title);

    // repasaże są gęstsze niż główna tabela: mniejsza czcionka i karty, a wiersz ma wysokość karty (bez dużych odstępów)
    var baseScale = computeScale(container, state, ctx, cols, bouts.filter(function (b) { return depth[b.id] === 0; }).length);
    var scale = Math.max(0.55, baseScale * 0.82);
    var fontPx = BASE_FONT_PX * scale;
    var rowPx = Math.round(fontPx * (ctx.editable ? 9.0 : 8.0));
    var halfPx = Math.max(1, Math.floor(rowPx / 2));
    var scroll = document.createElement('div');
    scroll.className = 'de-scroll';
    var grid = document.createElement('div');
    grid.className = 'de-grid';
    grid.style.fontSize = fontPx.toFixed(2) + 'px';
    grid.style.columnGap = Math.max(24, Math.round(36 * scale)) + 'px';
    grid.style.gridTemplateColumns = 'repeat(' + cols + ', ' + Math.round(BASE_COL_PX * scale) + 'px)';
    grid.style.gridTemplateRows = 'repeat(' + halfRows + ', ' + halfPx + 'px)';

    labels.forEach(function (l) {
      var el = document.createElement('div');
      el.className = 'de-comp-label';
      el.style.gridColumn = String(l.col + 1);
      el.style.gridRow = String(1 + l.row);
      el.textContent = l.text;
      grid.appendChild(el);
    });

    var cardById = {};
    bouts.forEach(function (b) {
      var hints = {};
      ['a', 'b'].forEach(function (k) {
        var spec = b.src[k];
        hints[k] = (spec.t === 'winner' ? 'Zwycięzca walki ' : 'Przegrany walki ') + numbers.byId[spec.bout];
      });
      var f = flow[b.id] || {};
      var parts = [];
      if (f.winner) parts.push('Zwycięzca → walka ' + f.winner);
      if (f.loser) parts.push((parts.length ? 'przegrany' : 'Przegrany') + ' → walka ' + f.loser);
      var slot = document.createElement('div');
      slot.className = 'de-slot';
      slot.style.gridColumn = String(depth[b.id] + 1);
      slot.style.gridRow = (1 + absTop[b.id]) + ' / span 2';
      var card = buildBout(bracket, b, 'Walka ' + numbers.byId[b.id] + ' · ' + b.title, hints, ctx, parts.join(' · '));
      cardById[b.id] = card;
      slot.appendChild(card);
      grid.appendChild(slot);
    });
    scroll.appendChild(grid);
    section.appendChild(scroll);
    container.appendChild(section);

    var edges = [];
    bouts.forEach(function (b, k) {
      ['a', 'b'].forEach(function (sideKey) {
        var spec = b.src[sideKey];
        if (spec.t !== 'winner' || !cardById[spec.bout]) return;     // tylko drzewo zwycięzców: bez przecięć
        edges.push({ from: cardById[spec.bout], to: cardById[b.id]._rows[sideKey], won: !!byId[spec.bout].winner });
      });
    });
    requestAnimationFrame(function () {
      if (grid.isConnected && grid.offsetWidth > 0) drawEdges(grid, edges);
    });
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
    var scale = computeScale(container, state, ctx, visible.length, base);
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

    var edges = [];
    for (var cr = 0; cr < cards.length - 1; cr++) {
      cards[cr].forEach(function (card, i) {
        edges.push({ from: card, to: cards[cr + 1][i >> 1]._rows[i % 2 === 0 ? 'a' : 'b'], won: !!card._winner });
      });
    }
    requestAnimationFrame(function () {
      if (grid.isConnected && grid.offsetWidth > 0) drawEdges(grid, edges);
      container.style.minHeight = '';
    });

    // repasaże: walki o miejsca, tabelka pod tabelką (patrz renderRepGroup)
    (bracket.repasaze || []).forEach(function (grp, gi) {
      renderRepGroup(container, bracket, grp, gi, numbers, state, ctx);
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
