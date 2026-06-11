export default function PageSelector({ totalPages, selectedPage, onPageChange, pagesList = [] }) {
  return (
    <div className="page-selector">
      <label htmlFor="page-select">Select Page</label>
      <select
        id="page-select"
        value={selectedPage}
        onChange={(e) => onPageChange(Number(e.target.value))}
      >
        {Array.from({ length: totalPages }, (_, i) => i + 1).map((num) => {
          const pageData = pagesList.find(p => p.page_num === num);
          const stationLabel = pageData && pageData.station !== "Unknown" 
            ? ` - STA ${pageData.station}` 
            : '';
            
          return (
            <option key={num} value={num}>
              Page {num}{stationLabel}
            </option>
          );
        })}
      </select>
    </div>
  );
}
