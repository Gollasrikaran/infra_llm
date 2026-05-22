import { useState, useEffect, useCallback } from 'react';
import './App.css';
import FileUpload from './components/FileUpload';
import MetricCard from './components/MetricCard';
import PageSelector from './components/PageSelector';
import AnalysisResult from './components/AnalysisResult';
import LoadingSkeleton from './components/LoadingSkeleton';

const API_BASE = '/api';

/* ═══════════════════════════════════════════════════════════════════════════
   HOME PAGE
   ═══════════════════════════════════════════════════════════════════════════ */

function HomePage({ onNavigate }) {
  return (
    <div className="fade-in">
      <div className="breadcrumb">
        <a href="#" onClick={(e) => { e.preventDefault(); onNavigate('home'); }}>Home</a>
        <span className="sep">›</span>
        <span className="breadcrumb-current">Dashboard</span>
      </div>
      <h1 className="page-title">Cross-Section Analyzer</h1>

      {/* Welcome banner */}
      <div className="home-banner fade-in-up">
        <div className="home-banner-content">
          <div className="home-banner-badge">🛣️ Highway Engineering AI</div>
          <h2 className="home-banner-heading">
            Analyze cross-sections<br />with Gemini Vision AI
          </h2>
          <p className="home-banner-desc">
            Upload highway engineering PDFs or images. Our AI identifies cut/fill regions,
            calculates trapezoidal areas, and extracts station data — instantly.
          </p>
          <button className="home-banner-btn" onClick={() => onNavigate('analyze')}>
            Get Started →
          </button>
        </div>
        <div className="home-banner-visual">
          <div className="home-visual-graphic">
            <div className="visual-line visual-line-1" />
            <div className="visual-line visual-line-2" />
            <div className="visual-fill-area" />
            <div className="visual-cut-area" />
            <div className="visual-label cut-label">CUT</div>
            <div className="visual-label fill-label">FILL</div>
          </div>
        </div>
      </div>

      {/* Stats row */}
      <div className="home-stats fade-in-up" style={{ animationDelay: '0.1s' }}>
        <div className="home-stat-card">
          <div className="home-stat-icon" style={{ background: '#e3f2fd' }}>📄</div>
          <div>
            <div className="home-stat-label">Supported Formats</div>
            <div className="home-stat-value">PDF, PNG, JPG</div>
          </div>
        </div>
        <div className="home-stat-card">
          <div className="home-stat-icon" style={{ background: '#e8f5e9' }}>🤖</div>
          <div>
            <div className="home-stat-label">AI Engine</div>
            <div className="home-stat-value">Gemini 2.5 Flash</div>
          </div>
        </div>
        <div className="home-stat-card">
          <div className="home-stat-icon" style={{ background: '#fff3e0' }}>📐</div>
          <div>
            <div className="home-stat-label">Area Method</div>
            <div className="home-stat-value">Trapezoidal Rule</div>
          </div>
        </div>
        <div className="home-stat-card">
          <div className="home-stat-icon" style={{ background: '#f3e5f5' }}>⚡</div>
          <div>
            <div className="home-stat-label">Analysis Speed</div>
            <div className="home-stat-value">~10 seconds</div>
          </div>
        </div>
      </div>

      {/* Feature cards */}
      <div className="home-features fade-in-up" style={{ animationDelay: '0.15s' }}>
        <div className="home-feature-card" onClick={() => onNavigate('analyze')}>
          <div className="home-feature-icon-wrap green">
            <span>📄</span>
          </div>
          <div className="home-feature-title">PDF Analysis</div>
          <div className="home-feature-desc">
            Upload multi-page engineering PDFs. Select any page, render it, and analyze
            cut/fill regions with AI vision.
          </div>
          <div className="home-feature-action">Start analyzing →</div>
        </div>

        <div className="home-feature-card" onClick={() => onNavigate('analyze')}>
          <div className="home-feature-icon-wrap blue">
            <span>🖼️</span>
          </div>
          <div className="home-feature-title">Image Analysis</div>
          <div className="home-feature-desc">
            Drop a PNG or JPG cross-section image directly. Get instant CUT/FILL
            identification and area calculations.
          </div>
          <div className="home-feature-action">Upload image →</div>
        </div>

        <div className="home-feature-card">
          <div className="home-feature-icon-wrap purple">
            <span>📊</span>
          </div>
          <div className="home-feature-title">Detailed Reports</div>
          <div className="home-feature-desc">
            View station info, catch points, slope ratios, sample elevations, and
            net cut/fill summaries for every intersection.
          </div>
          <div className="home-feature-action">View sample →</div>
        </div>
      </div>

      {/* How it works */}
      <div className="home-how fade-in-up" style={{ animationDelay: '0.2s' }}>
        <div className="card-header">
          <div className="card-title">How It Works</div>
        </div>
        <div className="home-steps">
          <div className="home-step">
            <div className="home-step-num">1</div>
            <div className="home-step-title">Upload</div>
            <div className="home-step-desc">Drop a PDF or image of a highway cross-section drawing</div>
          </div>
          <div className="home-step-arrow">→</div>
          <div className="home-step">
            <div className="home-step-num">2</div>
            <div className="home-step-title">Analyze</div>
            <div className="home-step-desc">Gemini Vision reads lines, slopes, and elevations from the drawing</div>
          </div>
          <div className="home-step-arrow">→</div>
          <div className="home-step">
            <div className="home-step-num">3</div>
            <div className="home-step-title">Results</div>
            <div className="home-step-desc">View CUT/FILL regions, areas, catch points, and net calculations</div>
          </div>
        </div>
      </div>
    </div>
  );
}


/* ═══════════════════════════════════════════════════════════════════════════
   MAIN APP
   ═══════════════════════════════════════════════════════════════════════════ */

function App() {
  // ── Navigation ──────────────────────────────────────────────────────────────
  const [currentPage, setCurrentPage] = useState('home');
  const [activeTab, setActiveTab] = useState('pdf');

  // ── Lightbox ───────────────────────────────────────────────────────────────
  const [zoomedImage, setZoomedImage] = useState(null); // url | null

  // ── PDF Analysis state ─────────────────────────────────────────────────────
  const [pdfFile, setPdfFile] = useState(null);
  const [fileId, setFileId] = useState(null);
  const [totalPages, setTotalPages] = useState(0);
  const [selectedPage, setSelectedPage] = useState(1);
  const [pageImageUrl, setPageImageUrl] = useState(null);
  const [pdfResult, setPdfResult] = useState(null);
  const [pdfError, setPdfError] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isAnalyzingPdf, setIsAnalyzingPdf] = useState(false);

  // ── Image Analysis state ───────────────────────────────────────────────────
  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [imageResult, setImageResult] = useState(null);
  const [imageError, setImageError] = useState(null);
  const [isAnalyzingImage, setIsAnalyzingImage] = useState(false);

  // ── Close lightbox on Escape ───────────────────────────────────────────────
  const closeLightbox = useCallback(() => setZoomedImage(null), []);
  useEffect(() => {
    if (!zoomedImage) return;
    const handler = (e) => { if (e.key === 'Escape') closeLightbox(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [zoomedImage, closeLightbox]);

  // ══════════════════════════════════════════════════════════════════════════
  // PDF UPLOAD
  // ══════════════════════════════════════════════════════════════════════════

  const handlePdfSelected = async (file) => {
    setPdfResult(null);
    setPdfError(null);
    setPageImageUrl(null);
    setFileId(null);
    setTotalPages(0);
    setSelectedPage(1);

    if (!file) {
      setPdfFile(null);
      return;
    }

    setPdfFile(file);
    setIsUploading(true);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const res = await fetch(`${API_BASE}/upload-pdf`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Upload failed');
      }

      const data = await res.json();
      setFileId(data.file_id);
      setTotalPages(data.total_pages);
      setSelectedPage(1);
    } catch (err) {
      setPdfError(err.message);
      setPdfFile(null);
    } finally {
      setIsUploading(false);
    }
  };

  // ══════════════════════════════════════════════════════════════════════════
  // PAGE PREVIEW
  // ══════════════════════════════════════════════════════════════════════════

  useEffect(() => {
    if (!fileId || !selectedPage) {
      setPageImageUrl(null);
      return;
    }
    setPageImageUrl(`${API_BASE}/pdf/${fileId}/page/${selectedPage}`);
    setPdfResult(null);
    setPdfError(null);
  }, [fileId, selectedPage]);

  // ══════════════════════════════════════════════════════════════════════════
  // ANALYZE PDF PAGE
  // ══════════════════════════════════════════════════════════════════════════

  const handleAnalyzePdf = async () => {
    if (!fileId || !selectedPage) return;

    setIsAnalyzingPdf(true);
    setPdfResult(null);
    setPdfError(null);

    try {
      const res = await fetch(`${API_BASE}/analyze/pdf-page`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_id: fileId, page_num: selectedPage }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Analysis failed');
      }

      const data = await res.json();
      if (data.success && data.data) {
        setPdfResult(data.data);
      } else {
        setPdfError(data.error || 'Could not parse Gemini response');
        if (data.raw) setPdfResult({ _raw: data.raw });
      }
    } catch (err) {
      setPdfError(err.message);
    } finally {
      setIsAnalyzingPdf(false);
    }
  };

  // ══════════════════════════════════════════════════════════════════════════
  // IMAGE UPLOAD + ANALYZE
  // ══════════════════════════════════════════════════════════════════════════

  const handleImageSelected = (file) => {
    setImageResult(null);
    setImageError(null);
    setImagePreview(null);

    if (!file) {
      setImageFile(null);
      return;
    }

    setImageFile(file);
    setImagePreview(URL.createObjectURL(file));
  };

  const handleAnalyzeImage = async () => {
    if (!imageFile) return;

    setIsAnalyzingImage(true);
    setImageResult(null);
    setImageError(null);

    try {
      const formData = new FormData();
      formData.append('file', imageFile);

      const res = await fetch(`${API_BASE}/analyze/image`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Analysis failed');
      }

      const data = await res.json();
      if (data.success && data.data) {
        setImageResult(data.data);
      } else {
        setImageError(data.error || 'Could not parse Gemini response');
        if (data.raw) setImageResult({ _raw: data.raw });
      }
    } catch (err) {
      setImageError(err.message);
    } finally {
      setIsAnalyzingImage(false);
    }
  };

  // ══════════════════════════════════════════════════════════════════════════
  // RENDER
  // ══════════════════════════════════════════════════════════════════════════

  return (
    <div className="app-layout">
      {/* ── Sidebar: Home + Analyze ──────────────────────────────────────── */}
      <aside className="sidebar">
        <div className="sidebar-logo">🛣️</div>

        <button
          className={`sidebar-btn ${currentPage === 'home' ? 'active' : ''}`}
          onClick={() => setCurrentPage('home')}
          title="Home"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
            <polyline points="9 22 9 12 15 12 15 22"/>
          </svg>
          <span className="sidebar-btn-label">Home</span>
        </button>

        <button
          className={`sidebar-btn ${currentPage === 'analyze' ? 'active' : ''}`}
          onClick={() => setCurrentPage('analyze')}
          title="Analyze"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="12" y1="18" x2="12" y2="12"/>
            <line x1="9" y1="15" x2="15" y2="15"/>
          </svg>
          <span className="sidebar-btn-label">Upload</span>
        </button>

        <div className="sidebar-spacer" />

        <button className="sidebar-btn" title="Help">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"/>
            <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
            <line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          <span className="sidebar-btn-label">Help</span>
        </button>
      </aside>

      <main className="main-content">
        {/* ═════════════════════════════════════════════════════════════════
            HOME PAGE
            ═════════════════════════════════════════════════════════════════ */}
        {currentPage === 'home' && (
          <HomePage onNavigate={setCurrentPage} />
        )}

        {/* ═════════════════════════════════════════════════════════════════
            ANALYZE PAGE
            ═════════════════════════════════════════════════════════════════ */}
        {currentPage === 'analyze' && (
          <div className="fade-in">
            {/* Top bar */}
            <div className="top-bar">
              <div className="top-tabs">
                <button
                  className={`top-tab ${activeTab === 'pdf' ? 'active' : ''}`}
                  onClick={() => setActiveTab('pdf')}
                >
                  <span className="top-tab-icon">📄</span> PDF Analysis
                </button>
                <button
                  className={`top-tab ${activeTab === 'image' ? 'active' : ''}`}
                  onClick={() => setActiveTab('image')}
                >
                  <span className="top-tab-icon">🖼️</span> Image Analysis
                </button>
              </div>
              <div className="top-actions">
                <button className="top-action-btn">⚡ Gemini Flash</button>
              </div>
            </div>

            {/* Breadcrumb + Title */}
            <div className="breadcrumb">
              <a href="#" onClick={(e) => { e.preventDefault(); setCurrentPage('home'); }}>Home</a>
              <span className="sep">›</span>
              <span>{activeTab === 'pdf' ? 'PDF Analysis' : 'Image Analysis'}</span>
            </div>
            <h1 className="page-title">Cross-Section Analyzer</h1>

            {/* ── TAB: PDF ───────────────────────────────────────────────── */}
            {activeTab === 'pdf' && (
              <div className="fade-in">
                {!fileId && (
                  <div className="card-grid">
                    <div className="card full-width" style={{ maxWidth: 600, margin: '0 auto' }}>
                      <div className="card-header">
                        <div>
                          <div className="card-title">Upload PDF</div>
                          <div className="card-subtitle">Highway engineering cross-section drawings</div>
                        </div>
                      </div>
                      <FileUpload
                        accept=".pdf"
                        label="Upload PDF"
                        hint="PDF files — highway engineering drawings"
                        onFileSelected={handlePdfSelected}
                        file={pdfFile}
                      />
                      {isUploading && (
                        <div className="loading-message" style={{ marginTop: '1rem' }}>
                          <span className="icon">📄</span>
                          Uploading and processing…
                        </div>
                      )}
                      {pdfError && !fileId && (
                        <div className="error-box">
                          <div className="title">Upload Error</div>
                          <div className="message">{pdfError}</div>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {fileId && totalPages > 0 && (
                  <>
                    <div className="metrics-row fade-in-up">
                      <MetricCard value={totalPages} label="Total Pages" />
                      <MetricCard value={totalPages * 5} label="Est. Sections" />
                      <MetricCard value="Gemini + CV" label="Engine" small />
                    </div>

                    <div className="content-grid">
                      <div className="card fade-in-up">
                        <div className="card-header">
                          <div>
                            <div className="card-title">Page Selection</div>
                            <div className="card-subtitle">{pdfFile?.name}</div>
                          </div>
                          <button
                            className="card-icon-btn"
                            title="Change PDF"
                            onClick={() => handlePdfSelected(null)}
                          >✕</button>
                        </div>

                        <PageSelector
                          totalPages={totalPages}
                          selectedPage={selectedPage}
                          onPageChange={setSelectedPage}
                        />

                        {pageImageUrl && (
                          <div className="page-preview">
                            <img src={pageImageUrl} alt={`Page ${selectedPage}`} loading="lazy" />
                            <button
                              className="preview-maximize-btn"
                              title="Maximize"
                              onClick={() => setZoomedImage(pageImageUrl)}
                            >
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                <polyline points="15 3 21 3 21 9"/>
                                <polyline points="9 21 3 21 3 15"/>
                                <line x1="21" y1="3" x2="14" y2="10"/>
                                <line x1="3" y1="21" x2="10" y2="14"/>
                              </svg>
                            </button>
                          </div>
                        )}

                        <button
                          className="btn-analyze"
                          onClick={handleAnalyzePdf}
                          disabled={isAnalyzingPdf || !fileId}
                        >
                          {isAnalyzingPdf ? (
                            <><span className="btn-spinner" /> Analyzing…</>
                          ) : (
                            <>🔍 Analyze This Page</>
                          )}
                        </button>
                      </div>

                      <div>
                        <div className="panel-label">Analysis Result</div>
                        {isAnalyzingPdf && <LoadingSkeleton />}
                        {pdfError && !isAnalyzingPdf && (
                          <div className="error-box">
                            <div className="title">Analysis Error</div>
                            <div className="message">{pdfError}</div>
                          </div>
                        )}
                        {pdfResult && !pdfResult._raw && !isAnalyzingPdf && (
                          <AnalysisResult data={pdfResult} />
                        )}
                        {pdfResult?._raw && !isAnalyzingPdf && (
                          <div>
                            <div className="error-box">
                              <div className="title">⚠ Could not parse JSON</div>
                              <div className="message">Raw Gemini response below</div>
                            </div>
                            <pre className="raw-json" style={{ marginTop: '12px' }}>{pdfResult._raw}</pre>
                          </div>
                        )}
                        {!pdfResult && !isAnalyzingPdf && !pdfError && (
                          <div className="empty-state">
                            <span className="empty-state-icon">📊</span>
                            <p>Select a page and click<br /><strong>Analyze This Page</strong></p>
                          </div>
                        )}
                      </div>
                    </div>
                  </>
                )}
              </div>
            )}

            {/* ── TAB: IMAGE ─────────────────────────────────────────────── */}
            {activeTab === 'image' && (
              <div className="fade-in">
                {!imageFile && (
                  <div className="card-grid">
                    <div className="card full-width" style={{ maxWidth: 600, margin: '0 auto' }}>
                      <div className="card-header">
                        <div>
                          <div className="card-title">Upload Image</div>
                          <div className="card-subtitle">PNG or JPG cross-section image</div>
                        </div>
                      </div>
                      <FileUpload
                        accept=".png,.jpg,.jpeg"
                        label="Upload Image"
                        hint="PNG, JPG — cross-section images"
                        onFileSelected={handleImageSelected}
                        file={imageFile}
                      />
                    </div>
                  </div>
                )}

                {imageFile && (
                  <div className="content-grid">
                    <div className="card fade-in-up">
                      <div className="card-header">
                        <div>
                          <div className="card-title">Uploaded Image</div>
                          <div className="card-subtitle">{imageFile.name}</div>
                        </div>
                        <button
                          className="card-icon-btn"
                          title="Remove"
                          onClick={() => handleImageSelected(null)}
                        >✕</button>
                      </div>

                      {imagePreview && (
                        <div className="image-preview">
                          <img src={imagePreview} alt={imageFile.name} />
                          <button
                            className="preview-maximize-btn"
                            title="Maximize"
                            onClick={() => setZoomedImage(imagePreview)}
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                              <polyline points="15 3 21 3 21 9"/>
                              <polyline points="9 21 3 21 3 15"/>
                              <line x1="21" y1="3" x2="14" y2="10"/>
                              <line x1="3" y1="21" x2="10" y2="14"/>
                            </svg>
                          </button>
                        </div>
                      )}

                      <button
                        className="btn-analyze"
                        onClick={handleAnalyzeImage}
                        disabled={isAnalyzingImage || !imageFile}
                      >
                        {isAnalyzingImage ? (
                          <><span className="btn-spinner" /> Analyzing…</>
                        ) : (
                          <>🔍 Analyze with Gemini</>
                        )}
                      </button>
                    </div>

                    <div>
                      <div className="panel-label">Gemini Vision Analysis</div>
                      {isAnalyzingImage && <LoadingSkeleton />}
                      {imageError && !isAnalyzingImage && (
                        <div className="error-box">
                          <div className="title">Analysis Error</div>
                          <div className="message">{imageError}</div>
                        </div>
                      )}
                      {imageResult && !imageResult._raw && !isAnalyzingImage && (
                        <AnalysisResult data={imageResult} />
                      )}
                      {imageResult?._raw && !isAnalyzingImage && (
                        <div>
                          <div className="error-box">
                            <div className="title">⚠ Could not parse JSON</div>
                            <div className="message">Raw Gemini response below</div>
                          </div>
                          <pre className="raw-json" style={{ marginTop: '12px' }}>{imageResult._raw}</pre>
                        </div>
                      )}
                      {!imageResult && !isAnalyzingImage && !imageError && (
                        <div className="empty-state">
                          <span className="empty-state-icon">📊</span>
                          <p>Upload an image and click<br /><strong>Analyze with Gemini</strong></p>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </main>

      {/* ── Lightbox ──────────────────────────────────────────────────────── */}
      {zoomedImage && (
        <div className="lightbox-overlay" onClick={closeLightbox}>
          <button className="lightbox-close" onClick={closeLightbox} title="Close (Esc)">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
          <img
            className="lightbox-img"
            src={zoomedImage}
            alt="Maximized view"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </div>
  );
}

export default App;
