import { useState, useRef } from 'react';

export default function FileUpload({ accept, label, hint, onFileSelected, file }) {
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef(null);

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) onFileSelected(droppedFile);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = () => setDragOver(false);

  const handleChange = (e) => {
    const selected = e.target.files[0];
    if (selected) onFileSelected(selected);
  };

  const handleRemove = (e) => {
    e.stopPropagation();
    onFileSelected(null);
    if (inputRef.current) inputRef.current.value = '';
  };

  const formatSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div>
      <div
        className={`upload-zone ${dragOver ? 'drag-over' : ''}`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          onChange={handleChange}
          style={{ display: 'none' }}
        />
        <span className="upload-icon">
          {accept?.includes('pdf') ? '📄' : '🖼️'}
        </span>
        <div className="upload-text">
          <strong>Click to upload</strong> or drag and drop
        </div>
        <div className="upload-hint">{hint || label}</div>
      </div>

      {file && (
        <div className="file-info fade-in">
          <span className="file-info-icon">
            {file.name.endsWith('.pdf') ? '📄' : '🖼️'}
          </span>
          <div className="file-info-details">
            <div className="file-info-name">{file.name}</div>
            <div className="file-info-meta">{formatSize(file.size)}</div>
          </div>
          <button className="file-remove-btn" onClick={handleRemove} title="Remove file">
            ✕
          </button>
        </div>
      )}
    </div>
  );
}
