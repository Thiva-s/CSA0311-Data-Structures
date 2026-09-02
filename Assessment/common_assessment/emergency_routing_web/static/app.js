const $ = (id) => document.getElementById(id);

async function api(url, options = {}) {
  const response = await fetch(url, { headers: {'Content-Type': 'application/json'}, ...options });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Request failed');
  return data;
}

function showError(element, error) {
  element.className = 'result error';
  element.textContent = error.message;
}

async function refreshStats() {
  const stats = await api('/api/stats');
  $('nodes').textContent = stats.nodes.toLocaleString();
  $('roads').textContent = `${stats.roads.toLocaleString()} roads`;
  $('cache').textContent = stats.cache_entries;
  $('seed-label').textContent = stats.seed === null ? 'RANDOMIZED' : `SEED ${stats.seed}`;
  $('source').max = $('destination').max = $('traffic-source').max = $('traffic-destination').max = stats.nodes - 1;
}

function renderPath(path) {
  const view = $('path-view');
  if (!path.length) { view.innerHTML = '<span class="path-placeholder">No route exists between these nodes.</span>'; return; }
  // Keep the UI readable for very long routes while retaining the exact result above.
  const visible = path.length > 18 ? [...path.slice(0, 8), '…', ...path.slice(-8)] : path;
  view.innerHTML = visible.map((node, index) => {
    const isEnd = index === visible.length - 1;
    const value = node === '…' ? '<b>…</b>' : `<b>${node}</b>`;
    return `${index ? '<i class="connector"></i>' : ''}<span class="path-node ${isEnd ? 'end' : ''}">${value}</span>`;
  }).join('');
}

$('route-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const resultBox = $('route-result');
  resultBox.className = 'result'; resultBox.textContent = 'Calculating shortest route…';
  try {
    const result = await api('/api/route', {method:'POST', body:JSON.stringify({source:+$('source').value, destination:+$('destination').value})});
    resultBox.className = 'result';
    resultBox.innerHTML = result.reachable
      ? `<strong>${result.distance.toLocaleString()} sec</strong> &nbsp; fastest travel time<br>${result.path_length} road segments · ${result.cached ? 'served from cache' : 'calculated by Dijkstra'} · ${result.elapsed_ms} ms`
      : 'No route could be found between those nodes.';
    $('path-meta').textContent = result.reachable ? `${result.path.length} nodes · ${result.elapsed_ms} ms` : 'Unreachable';
    renderPath(result.path); await refreshStats();
  } catch (error) { showError(resultBox, error); }
});

$('traffic-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const resultBox = $('traffic-result'); resultBox.className = 'result'; resultBox.textContent = 'Applying traffic update…';
  try {
    const result = await api('/api/traffic', {method:'POST', body:JSON.stringify({source:+$('traffic-source').value, destination:+$('traffic-destination').value, weight:+$('weight').value})});
    resultBox.className = 'result'; resultBox.innerHTML = `<strong>UPDATE APPLIED</strong><br>Road ${$('traffic-source').value} ↔ ${$('traffic-destination').value} is now ${$('weight').value} seconds. ${result.cache_cleared} cached route(s) cleared.`;
    await refreshStats();
  } catch (error) { showError(resultBox, error); }
});

$('generate-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = event.submitter; button.disabled = true; button.textContent = 'Generating…';
  try {
    const body = {nodes:+$('gen-nodes').value, roads:+$('gen-roads').value, max_weight:+$('gen-weight').value};
    if ($('gen-seed').value.trim()) body.seed = +$('gen-seed').value;
    await api('/api/generate', {method:'POST', body:JSON.stringify(body)});
    $('route-result').className = 'result empty'; $('route-result').textContent = 'Network regenerated. Run a route query.';
    $('traffic-result').className = 'result empty'; $('traffic-result').textContent = 'Updating a road clears cached routes so new conditions are used.';
    $('path-view').innerHTML = '<span class="path-placeholder">Your selected route will appear here</span>';
    $('path-meta').textContent = 'No route calculated'; await refreshStats();
  } catch (error) { showError($('route-result'), error); } finally { button.disabled = false; button.textContent = 'Regenerate network'; }
});

refreshStats().catch((error) => showError($('route-result'), error));
