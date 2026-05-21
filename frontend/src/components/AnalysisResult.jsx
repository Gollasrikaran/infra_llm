import { useState } from 'react';

function safeWidth(lx, rx) {
  try {
    const w = Math.abs(parseFloat(rx) - parseFloat(lx));
    return isNaN(w) ? '—' : `${w.toFixed(1)} ft`;
  } catch {
    return '—';
  }
}

function formatArea(val) {
  if (val == null) return '—';
  return `${val.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })} sq ft`;
}

function SamplePointsTable({ samples }) {
  const [open, setOpen] = useState(false);
  if (!samples || samples.length === 0) return null;

  return (
    <div className="expandable">
      <button className="expand-btn" onClick={() => setOpen(!open)}>
        <span className={`expand-arrow ${open ? 'open' : ''}`}>▶</span>
        📊 Trapezoidal Sample Points ({samples.length})
      </button>
      {open && (
        <div className="expand-content">
          <table className="sample-table">
            <thead>
              <tr>
                <th>Offset (ft)</th>
                <th>Existing Elev (ft)</th>
                <th>Proposed Elev (ft)</th>
                <th>Gap (ft)</th>
              </tr>
            </thead>
            <tbody>
              {samples.map((s, i) => (
                <tr key={i}>
                  <td>{s.x ?? '—'}</td>
                  <td>{s.existing_elev ?? '—'}</td>
                  <td>{s.proposed_elev ?? '—'}</td>
                  <td>{s.gap ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function IntersectionCard({ region, index }) {
  const rid = region.id ?? index + 1;
  const rtype = (region.type || 'UNKNOWN').toUpperCase();
  const lcp = region.left_catch_point || {};
  const rcp = region.right_catch_point || {};
  const areaCalc = region.area_calculation || {};
  const totalArea = areaCalc.total_area_sqft;
  const samples = areaCalc.sample_points || [];
  const notes = region.notes;

  let cardClass, icon, desc;
  if (rtype === 'CUT') {
    cardClass = 'cut';
    icon = '🔴';
    desc = 'Proposed grade is BELOW existing ground — excavation needed';
  } else if (rtype === 'FILL') {
    cardClass = 'fill';
    icon = '🟢';
    desc = 'Proposed grade is ABOVE existing ground — fill material needed';
  } else {
    cardClass = 'unknown';
    icon = '⚪';
    desc = 'Undetermined';
  }

  return (
    <div className={`intersection-card ${cardClass}`}>
      <div className="intersection-id">Intersection {rid}</div>
      <div className={`intersection-type ${cardClass}`}>
        {icon} {rtype}
      </div>
      <div className="intersection-desc">{desc}</div>

      <div className="info-grid">
        <div className="info-item">
          <div className="k">Left Catch Point</div>
          <div className="v">
            x = {lcp.x ?? '—'} ft &nbsp;|&nbsp; elev = {lcp.elevation ?? '—'} ft
          </div>
        </div>
        <div className="info-item">
          <div className="k">Right Catch Point</div>
          <div className="v">
            x = {rcp.x ?? '—'} ft &nbsp;|&nbsp; elev = {rcp.elevation ?? '—'} ft
          </div>
        </div>
        <div className="info-item">
          <div className="k">Width</div>
          <div className="v">{safeWidth(lcp.x, rcp.x)}</div>
        </div>
        <div className="info-item">
          <div className="k">Area (Gemini estimate)</div>
          <div className="v large">{formatArea(totalArea)}</div>
        </div>
      </div>

      <SamplePointsTable samples={samples} />

      {notes && (
        <div className="info-item" style={{ marginTop: '0.5rem' }}>
          <div className="k">Notes</div>
          <div className="v">{notes}</div>
        </div>
      )}
    </div>
  );
}

function SummaryPanel({ intersections }) {
  const cutTotal = intersections
    .filter((r) => (r.type || '').toUpperCase() === 'CUT')
    .reduce((s, r) => s + ((r.area_calculation || {}).total_area_sqft || 0), 0);

  const fillTotal = intersections
    .filter((r) => (r.type || '').toUpperCase() === 'FILL')
    .reduce((s, r) => s + ((r.area_calculation || {}).total_area_sqft || 0), 0);

  const net = cutTotal - fillTotal;
  const netClass = net > 0 ? 'net-cut' : net < 0 ? 'net-fill' : 'net-zero';

  return (
    <div className="summary-panel">
      <div className="summary-title">Gemini Summary</div>
      <div className="summary-row">
        <div className="summary-item">
          <div className="label">Total CUT</div>
          <div className="value cut">{formatArea(cutTotal)}</div>
        </div>
        <div className="summary-item">
          <div className="label">Total FILL</div>
          <div className="value fill">{formatArea(fillTotal)}</div>
        </div>
        <div className="summary-item">
          <div className="label">Net (CUT − FILL)</div>
          <div className={`value ${netClass}`}>
            {net >= 0 ? '+' : ''}{formatArea(Math.abs(net))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AnalysisResult({ data }) {
  const [showRaw, setShowRaw] = useState(false);

  if (!data) return null;

  const station = data.station || '—';
  const slopes = data.slopes || '—';
  const extent = data.proposed_grade_extent || '—';
  const egLine = data.existing_ground_line || '—';
  const nRegions = data.total_intersections || 0;
  const intersections = data.intersections || [];

  return (
    <div className="result-panel">
      {/* Station header */}
      <div className="station-header">
        <div className="station-grid">
          <div className="station-item">
            <div className="label">Station</div>
            <div className="value highlight">{station}</div>
          </div>
          <div className="station-item">
            <div className="label">Slopes</div>
            <div className="value">{slopes}</div>
          </div>
          <div className="station-item">
            <div className="label">Proposed Grade Extent</div>
            <div className="value">{extent}</div>
          </div>
          <div className="station-item">
            <div className="label">Regions Found</div>
            <div className="value highlight">{nRegions}</div>
          </div>
        </div>
        <div className="station-divider">
          <span className="label">Existing Ground — </span>
          <span className="value">{egLine}</span>
        </div>
      </div>

      {/* Intersection cards */}
      {intersections.map((region, i) => (
        <IntersectionCard key={region.id ?? i} region={region} index={i} />
      ))}

      {/* Summary */}
      {intersections.length > 0 && <SummaryPanel intersections={intersections} />}

      {/* Reasoning */}
      {data.reasoning && (
        <div className="section-block">
          <div className="section-hdr">Reasoning</div>
          <div className="section-content">{data.reasoning}</div>
        </div>
      )}

      {/* Notes */}
      {data.notes && (
        <div className="section-block">
          <div className="section-hdr">Notes</div>
          <div className="section-content">{data.notes}</div>
        </div>
      )}

      {/* Raw JSON */}
      <div className="expandable" style={{ marginTop: '1rem' }}>
        <button className="expand-btn" onClick={() => setShowRaw(!showRaw)}>
          <span className={`expand-arrow ${showRaw ? 'open' : ''}`}>▶</span>
          Raw JSON
        </button>
        {showRaw && (
          <div className="expand-content">
            <pre className="raw-json">{JSON.stringify(data, null, 2)}</pre>
          </div>
        )}
      </div>
    </div>
  );
}
