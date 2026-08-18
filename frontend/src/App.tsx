import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { 
  Upload, 
  AlertCircle, 
  FileText, 
  Check, 
  X, 
  Database, 
  ChevronDown, 
  ChevronRight, 
  Eye, 
  FileSearch, 
  Loader2, 
  Coins, 
  Cpu, 
  Activity, 
  Terminal, 
  FileCheck2, 
  ShieldCheck,
  Sparkles,
  Download
} from 'lucide-react';

interface Conflict {
  id: string;
  run_id?: string;
  topic: string;
  ai_reasoning: string;
  status: string;
  fact_a_text?: string;
  fact_b_text?: string;
  document_id?: string;
  doc_a_id?: string;
  doc_b_id?: string;
}

interface Fact {
  id: string;
  document_id: string;
  document_name?: string;
  key?: string;
  value?: string;
  paragraph_text?: string;
  page_number?: string;
}

interface RunTelemetry {
  id: string | null;
  status: string;
  current_stage: string;
  total_cost: number;
  total_tokens: number;
}

const API_BASE_URL = 'http://127.0.0.1:8000/api/v1';

export default function App() {
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [facts, setFacts] = useState<Fact[]>([]);
  const [currentDocumentText, setCurrentDocumentText] = useState<string>(
    "// DOCTASK AUDIT DESK\n// Ready for ingestion.\n// Upload a source contract or select a pending conflict to load baseline document context."
  );
  const [telemetry, setTelemetry] = useState<RunTelemetry>({
    id: null,
    status: 'IDLE',
    current_stage: 'READY',
    total_cost: 0.0,
    total_tokens: 0.0,
  });
  
  const [file, setFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isFetchingText, setIsFetchingText] = useState(false);
  const [exportFormat, setExportFormat] = useState<'md' | 'txt' | 'json'>('md');
  const [isExporting, setIsExporting] = useState(false);
  
  const [factsExpanded, setFactsExpanded] = useState(true);
  const [activeConflict, setActiveConflict] = useState<Conflict | null>(null);

  // AI Active state detector
  const isAiThinking = isProcessing || [
    'upload', 
    'guardrail_sanitizer', 
    'extract_facts', 
    'detect_conflicts',
    'classifying',
    'extracting'
  ].includes((telemetry.current_stage || '').toLowerCase());

  const fetchData = async () => {
    try {
      const [conflictsRes, factsRes, runsRes] = await Promise.all([
        axios.get(`${API_BASE_URL}/conflicts/pending`),
        axios.get(`${API_BASE_URL}/facts/`),
        axios.get(`${API_BASE_URL}/runs/latest`)
      ]);
      setConflicts(conflictsRes.data || []);
      setFacts(factsRes.data || []);
      if (runsRes.data) {
        setTelemetry(runsRes.data);
      }
      
      if (activeConflict && !(conflictsRes.data || []).find((c: Conflict) => c.id === activeConflict.id)) {
        setActiveConflict(null);
      }
    } catch (error) {
      console.error("Failed to fetch data:", error);
    }
  };

  useEffect(() => {
    fetchData(); 
    const interval = setInterval(fetchData, 2000);
    return () => clearInterval(interval);
  }, []); 

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setIsProcessing(true);
    const isPdf = file.name.toLowerCase().endsWith('.pdf') || file.type === 'application/pdf';
    
    if (isPdf) {
      setCurrentDocumentText(`[INGESTING BINARY PDF: ${file.name}]\nExtracting text layers and dispatching LangGraph multi-node audit...`);
      setActiveConflict(null);
    } else {
      const reader = new FileReader();
      reader.onload = (event) => {
        if (event.target?.result) {
          setCurrentDocumentText(event.target.result as string);
          setActiveConflict(null);
        }
      };
      reader.readAsText(file);
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
      const uploadRes = await axios.post(`${API_BASE_URL}/upload/`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      
      const docId = uploadRes.data?.document_id;
      setFile(null);

      setTimeout(async () => {
        if (docId) {
          try {
            const textRes = await axios.get(`${API_BASE_URL}/conflicts/document-text/${docId}`);
            if (textRes.data?.text) {
              setCurrentDocumentText(textRes.data.text);
            }
          } catch (err) {
            console.error("Could not fetch parsed document text:", err);
          }
        }
        setIsProcessing(false);
      }, 3000);

    } catch (error) {
      console.error("Upload failed:", error);
      setCurrentDocumentText("// FATAL ERROR: UPLOAD FAILED.");
      setIsProcessing(false);
    }
  };

  const handleConflictClick = async (conflict: Conflict) => {
    setActiveConflict(conflict);
    const targetDocId = conflict.doc_a_id || conflict.document_id;
    if (!targetDocId) return;
    
    setIsFetchingText(true);
    try {
      const response = await axios.get(`${API_BASE_URL}/conflicts/document-text/${targetDocId}`);
      if (response.data?.text) {
        setCurrentDocumentText(response.data.text);
      }
    } catch (error) {
      console.error("Failed to fetch baseline document text:", error);
    }
    setIsFetchingText(false);
  };

  const resolveConflict = useCallback(async (conflictId: string, resolutionStatus: string) => {
    const targetConflict = conflicts.find(c => c.id === conflictId) || activeConflict;
    
    try {
      await axios.post(`${API_BASE_URL}/conflicts/${conflictId}/resolve`, {
        status: resolutionStatus.toUpperCase(),
        decision: resolutionStatus.toUpperCase()
      });
      
      // If approved (Override), mutate active document text directly on screen
      if (resolutionStatus.toUpperCase() === 'RESOLVED_KEPT_B' && targetConflict) {
        const oldText = (targetConflict.fact_a_text || "").trim();
        const newText = (targetConflict.fact_b_text || "").trim();

        if (oldText && newText && currentDocumentText.toLowerCase().includes(oldText.toLowerCase())) {
          const regex = new RegExp(oldText.replace(/[-/\\^$*+?.()|[\]{}]/g, '\\$&'), 'i');
          setCurrentDocumentText(prev => prev.replace(regex, newText));
        }
      }

      setConflicts(prev => prev.filter(c => c.id !== conflictId));
      if (activeConflict?.id === conflictId) {
        setActiveConflict(null);
      }
      fetchData();
    } catch (error) {
      console.error("Resolution failed:", error);
    }
  }, [activeConflict, conflicts, currentDocumentText]);

  // Keyboard shortcut listeners
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!activeConflict) return;
      if (e.key === 'o' || e.key === 'O') {
        resolveConflict(activeConflict.id, 'RESOLVED_KEPT_B');
      } else if (e.key === 'r' || e.key === 'R') {
        resolveConflict(activeConflict.id, 'RESOLVED_KEPT_A');
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [activeConflict, resolveConflict]);

  // Download finalized report
  const handleDownloadReport = async () => {
    setIsExporting(true);
    try {
      const response = await axios.get(`${API_BASE_URL}/runs/report/export?format=${exportFormat}`, {
        responseType: 'blob',
      });

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `final_audit_report.${exportFormat}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Failed to export final report:', error);
    } finally {
      setIsExporting(false);
    }
  };

  // Baseline Document Inline Strikethrough & Insertion Diffing
  const renderInlineDiffDocument = () => {
    if (!activeConflict) {
      return currentDocumentText;
    }

    const oldText = (activeConflict.fact_a_text || "").trim();
    const newText = (activeConflict.fact_b_text || "").trim();

    if (!oldText || !currentDocumentText) {
      return currentDocumentText;
    }

    const lowerDoc = currentDocumentText.toLowerCase();
    const lowerOld = oldText.toLowerCase();
    const matchIndex = lowerDoc.indexOf(lowerOld);

    if (matchIndex === -1) {
      return (
        <>
          <div className="mb-4 p-3 bg-yellow-50 border-2 border-black font-bold text-xs flex items-center justify-between">
            <span>⚠️ Context: Baseline fact verified in historical memory.</span>
            <span className="bg-[#00E599] px-2 py-0.5 border border-black text-[10px] uppercase font-black">
              New Fact: {newText}
            </span>
          </div>
          {currentDocumentText}
        </>
      );
    }

    const before = currentDocumentText.substring(0, matchIndex);
    const matchedOriginal = currentDocumentText.substring(matchIndex, matchIndex + oldText.length);
    const after = currentDocumentText.substring(matchIndex + oldText.length);

    return (
      <>
        {before}
        <span className="inline-flex items-center align-middle mx-1 whitespace-normal text-black font-black">
          <del className="bg-[#FF4A4A] text-white px-2 py-0.5 border-2 border-black border-r-0 decoration-black decoration-2 line-through shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
            {matchedOriginal}
          </del>
          <ins className="bg-[#00E599] text-black px-2 py-0.5 border-2 border-black no-underline shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
            {newText}
          </ins>
        </span>
        {after}
      </>
    );
  };

  return (
    <>
      <style dangerouslySetInnerHTML={{__html: `
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700;900&family=JetBrains+Mono:wght@400;500;700;800&display=swap');
        
        .brutalist-scrollbar::-webkit-scrollbar { width: 10px; height: 10px; }
        .brutalist-scrollbar::-webkit-scrollbar-track { background: #EAEAE8; border-left: 2px solid black; }
        .brutalist-scrollbar::-webkit-scrollbar-thumb { background-color: black; border: 2px solid #EAEAE8; }
      `}} />

      <div className="min-h-screen bg-[#EFEFED] text-black font-['Space_Grotesk',sans-serif] selection:bg-[#FFE600] selection:text-black flex flex-col relative overflow-x-hidden antialiased">
        
        {/* FULLSCREEN UPLOAD PROCESSING OVERLAY */}
        {isProcessing && (
          <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-[#FFCC00] border-8 border-black transition-all duration-0">
            <div className="bg-white border-4 border-black shadow-[12px_12px_0px_0px_rgba(0,0,0,1)] p-12 max-w-lg w-full flex flex-col items-center text-center">
              <img 
                src="/loading.gif" 
                alt="Processing..." 
                className="object-cover mb-8 border-4 border-black shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
                onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
              />
              <h2 className="text-5xl font-black uppercase tracking-tighter mb-4 text-black">Auditing</h2>
              <p className="text-lg font-bold text-black border-2 border-black bg-[#E9FF70] px-4 py-2 inline-flex items-center gap-2 uppercase shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]">
                <FileSearch size={20} strokeWidth={3} />
                Enforcing Memory Checks
              </p>
            </div>
          </div>
        )}

        {/* TOP HEADER */}
        <header className="bg-white border-b-4 border-black px-6 py-3.5 flex items-center justify-between z-20 sticky top-0 shadow-[0_4px_0px_0px_rgba(0,0,0,1)]">
          <div className="flex items-center gap-3">
            <img 
              src="/doc.png" 
              alt="DocTask Logo" 
              className="w-12 h-12 object-contain shrink-0" 
              onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
            />
            <div className="flex flex-col">
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-black uppercase tracking-tight text-black flex items-center gap-1.5">
                  DOCTASK<span className="text-[#FF2E5B]">.AGENT</span>
                </h1>
                <span className="bg-black text-[#FFE600] text-[9px] font-mono font-black uppercase px-2 py-0.5 tracking-widest border border-black">
                  PROD
                </span>
              </div>
              <span className="text-[10px] font-mono text-gray-600 font-bold uppercase tracking-wider">
                Continuous Document Intelligence & Review Gate
              </span>
            </div>
          </div>

          {/* TELEMETRY BAR & EXPORT CONTROLS */}
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2.5 bg-[#FAF8F5] border-2 border-black px-3.5 py-1.5 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]">
              <Activity size={15} className="text-blue-600 animate-pulse" strokeWidth={3} />
              <div className="flex flex-col">
                <span className="font-mono font-bold text-gray-500 uppercase text-[9px] leading-none">STAGE</span>
                <span className="font-mono font-black uppercase tracking-wider text-xs leading-tight">
                  {telemetry.current_stage || 'READY'}
                </span>
              </div>
            </div>

            <div className="hidden md:flex items-center gap-2.5 bg-[#FAF8F5] border-2 border-black px-3.5 py-1.5 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]">
              <Cpu size={15} className="text-purple-600" strokeWidth={2.5} />
              <div className="flex flex-col">
                <span className="font-mono font-bold text-gray-500 uppercase text-[9px] leading-none">TOKENS</span>
                <span className="font-mono font-black text-xs leading-tight">
                  {telemetry.total_tokens.toLocaleString()}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-2.5 bg-[#FAF8F5] border-2 border-black px-3.5 py-1.5 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]">
              <Coins size={15} className="text-emerald-600" strokeWidth={2.5} />
              <div className="flex flex-col">
                <span className="font-mono font-bold text-gray-500 uppercase text-[9px] leading-none">RUN SPEND</span>
                <span className="font-mono font-black text-xs text-emerald-600 leading-tight">
                  ${telemetry.total_cost.toFixed(4)} <span className="text-[9px] text-black font-bold">USD</span>
                </span>
              </div>
            </div>

            {/* EXPORT REPORT CONTROLLER */}
            <div className="flex items-center border-2 border-black bg-[#FAF8F5] shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]">
              <select
                value={exportFormat}
                onChange={(e) => setExportFormat(e.target.value as 'md' | 'txt' | 'json')}
                className="bg-transparent text-xs font-mono font-black uppercase px-2.5 py-2 border-r-2 border-black outline-none cursor-pointer hover:bg-[#EAEAE8] transition-colors"
              >
                <option value="md">.MD</option>
                <option value="txt">.TXT</option>
                <option value="json">.JSON</option>
              </select>

              <button
                onClick={handleDownloadReport}
                disabled={isExporting}
                className="flex items-center gap-1.5 bg-[#FFE600] hover:bg-yellow-400 text-black px-3 py-2 text-xs font-mono font-black uppercase active:translate-x-[1px] active:translate-y-[1px] transition-all disabled:opacity-50"
              >
                {isExporting ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} strokeWidth={3} />}
                <span>{isExporting ? 'EXPORTING...' : 'EXPORT'}</span>
              </button>
            </div>

            <div className="flex items-center gap-2 bg-[#00E599] border-2 border-black text-black px-3.5 py-2 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]">
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-black opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-black"></span>
              </span>
              <span className="text-[11px] font-mono font-black uppercase tracking-widest leading-none">
                LIVE SYNC
              </span>
            </div>
          </div>
        </header>

        {/* WORKSPACE */}
        <main className="flex-grow flex flex-col lg:flex-row h-[calc(100vh-73px)] w-full">
          
          {/* --- LEFT SIDEBAR --- */}
          <aside className="w-full lg:w-[460px] bg-white border-r-4 border-black flex flex-col h-full overflow-y-auto brutalist-scrollbar z-10 shrink-0">
            <div className="p-6 space-y-8">
              
              {/* Ingestion Dropzone */}
              <section className="space-y-3">
                <div className="flex items-center justify-between border-b-2 border-black pb-2">
                  <h2 className="text-xs font-mono font-black uppercase tracking-widest text-black flex items-center gap-2">
                    <Upload size={16} strokeWidth={2.5} /> 01. INGESTION PIPELINE
                  </h2>
                  <span className="text-[10px] font-mono bg-black text-white px-2 py-0.5 font-bold uppercase">
                    AUTO-HASH
                  </span>
                </div>

                <form onSubmit={handleUpload} className="space-y-3">
                  <label className="flex flex-col items-center justify-center w-full min-h-[90px] transition-all bg-[#FAF8F5] border-2 border-dashed border-black hover:bg-[#E9FF70] cursor-pointer group p-4 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]">
                    <div className="flex items-center gap-3 w-full">
                      <div className="w-9 h-9 bg-white border-2 border-black flex items-center justify-center shrink-0">
                        <FileText size={18} strokeWidth={2.5} />
                      </div>
                      <div className="flex flex-col truncate">
                        <span className="text-xs font-black uppercase truncate text-black">
                          {file ? file.name : "SELECT SOURCE DOCUMENT"}
                        </span>
                        <span className="text-[10px] font-mono text-gray-500 font-bold uppercase">
                          {file ? `${(file.size / 1024).toFixed(1)} KB · READY TO AUDIT` : "TXT · MD · DOCX · PDF"}
                        </span>
                      </div>
                    </div>
                    <input 
                      type="file" 
                      className="hidden" 
                      onChange={(e) => setFile(e.target.files?.[0] || null)}
                    />
                  </label>
                  
                  <button 
                    type="submit" 
                    disabled={!file || isProcessing} 
                    className="w-full bg-[#FFE600] text-black border-2 border-black text-xs font-black uppercase tracking-widest py-3.5 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] hover:translate-y-[2px] hover:translate-x-[2px] hover:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] active:translate-y-[4px] active:translate-x-[4px] active:shadow-none disabled:opacity-50 disabled:pointer-events-none transition-all flex items-center justify-center gap-2"
                  >
                    <Terminal size={16} strokeWidth={2.5} />
                    {isProcessing ? 'DISPATCHING AUDIT...' : 'EXECUTE AGENTIC AUDIT'}
                  </button>
                </form>
              </section>

              {/* Verified Facts */}
              <section className="space-y-3">
                <button 
                  onClick={() => setFactsExpanded(!factsExpanded)} 
                  className="w-full flex items-center justify-between text-black border-b-2 border-black pb-2 hover:bg-[#FAF8F5] transition-colors"
                >
                  <h2 className="text-xs font-mono font-black uppercase tracking-widest flex items-center gap-2">
                    <Database size={16} strokeWidth={2.5} /> 02. VERIFIED FACTS ({facts.length})
                  </h2>
                  {factsExpanded ? <ChevronDown size={18} strokeWidth={2.5} /> : <ChevronRight size={18} strokeWidth={2.5} />}
                </button>
                
                {factsExpanded && (
                  <div className="bg-[#FAF8F5] border-2 border-black p-3.5 max-h-[260px] overflow-y-auto brutalist-scrollbar shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] space-y-3">
                    {facts.length === 0 ? (
                      <div className="text-[11px] font-mono font-bold uppercase tracking-widest text-center py-6 text-gray-500">
                        // NO PERSISTED FACTS IN CORPUS
                      </div>
                    ) : (
                      facts.map((fact) => (
                        <div key={fact.id} className="p-3 bg-white border-2 border-black shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] flex flex-col gap-2">
                          <div className="flex items-center justify-between border-b border-black pb-1.5">
                            <span className="font-mono font-black text-black uppercase tracking-wider text-[9px] bg-[#D1FF26] border border-black px-2 py-0.5">
                              {fact.key?.replace(/_/g, ' ') || 'EXTRACTED STATEMENT'}
                            </span>
                            <span className="font-mono font-bold text-[9px] text-gray-600 uppercase">
                              PAGE {fact.page_number || '1'}
                            </span>
                          </div>
                          
                          <p className="font-bold text-xs leading-snug text-black break-words">
                            {fact.value || 'No value recorded'}
                          </p>

                          {fact.paragraph_text && (
                            <div className="font-mono text-[10px] text-gray-600 bg-[#FAF8F5] p-2 border border-black/30 italic break-words">
                              "{fact.paragraph_text}"
                            </div>
                          )}

                          <div className="flex items-center gap-1.5 text-[9px] font-mono font-bold text-black border-t border-black/20 pt-1.5">
                            <FileCheck2 size={11} strokeWidth={2.5} />
                            <span className="truncate">{fact.document_name || "CORPUS_SOURCE_DOC"}</span>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </section>

              {/* Review Gate with Thinking GIF */}
              <section className="space-y-3 pb-6">
                <header className="flex items-center justify-between border-b-2 border-black pb-2">
                  <h2 className="text-xs font-mono font-black uppercase tracking-widest text-black flex items-center gap-2">
                    <AlertCircle size={16} strokeWidth={2.5} /> 03. REVIEW GATE
                  </h2>
                  <span className={`text-[10px] font-mono font-black tracking-widest px-2.5 py-0.5 uppercase border-2 border-black shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] ${
                    conflicts.length > 0 ? 'bg-[#FF2E5B] text-white animate-pulse' : 'bg-[#00E599] text-black'
                  }`}>
                    {conflicts.length} PENDING
                  </span>
                </header>

                {/* AI Auditing / Memory Thinking GIF Card */}
                {isAiThinking ? (
                  <div className=" border-3 border-black p-5 flex flex-col items-center justify-center text-center gap-3 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
                    <img 
                      src="/public/boxer.gif" 
                      alt="AI Analyzing Reviews..." 
                      className="object-contain border-2 border-black shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] "
                      // onError={(e) => {
                      //   const img = e.target as HTMLImageElement;
                      //   if (!img.src.includes('loading.gif')) {
                      //     img.src = '/loading.gif';
                      //   }
                      // }}
                    />
                    <div className="flex flex-col gap-1">
                      <span className="text-xs font-black uppercase tracking-wider text-black flex items-center justify-center gap-1.5">
                        <Sparkles size={14} className="text-yellow-600 animate-spin" />
                        CROSS-REFERENCING MEMORY...
                      </span>
                      <span className="text-[10px] font-mono text-gray-700 font-bold uppercase">
                        Active Stage: {telemetry.current_stage || 'AUDITING CONFLICTS'}
                      </span>
                    </div>
                  </div>
                ) : conflicts.length === 0 ? (
                  <div className="bg-white border-2 border-black border-dashed p-6 flex flex-col items-center justify-center text-center gap-2">
                    <div className="w-10 h-10 bg-[#00E599] border-2 border-black flex items-center justify-center shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]">
                      <ShieldCheck size={24} className="text-black" strokeWidth={2.5} />
                    </div>
                    <p className="text-xs font-black tracking-widest text-black uppercase mt-1">SYSTEM IN FULL HARMONY</p>
                    <span className="text-[10px] font-mono text-gray-500 uppercase font-bold">No active anomalies or contradictions detected</span>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {conflicts.map((conflict) => (
                      <article 
                        key={conflict.id} 
                        onClick={() => handleConflictClick(conflict)}
                        className={`border-2 border-black p-4 cursor-pointer transition-all shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] flex flex-col gap-2
                          ${activeConflict?.id === conflict.id 
                            ? 'bg-[#FFE600] translate-x-[2px] translate-y-[2px] shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]' 
                            : 'bg-white hover:bg-[#FAF8F5]'}`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-[9px] font-mono font-black uppercase bg-red-100 text-red-700 border border-red-700 px-2 py-0.5">
                            CONTRADICTION
                          </span>
                          <span className="text-[9px] font-mono font-bold text-gray-500 uppercase">
                            CLICK TO INSPECT BASELINE
                          </span>
                        </div>
                        <h3 className="text-xs font-black text-black uppercase leading-tight break-words">{conflict.topic}</h3>
                        <p className="text-[11px] text-gray-800 font-mono leading-relaxed bg-white/70 p-2 border border-black/30 break-words">
                          {conflict.ai_reasoning}
                        </p>
                      </article>
                    ))}
                  </div>
                )}
              </section>
            </div>
          </aside>

          {/* --- RIGHT MAIN SECTION: CANVAS & DOCKED COMMAND CENTER --- */}
          <section className="flex-grow flex flex-col bg-[#EFEFED] relative overflow-hidden w-full min-w-0">
            <header className="px-6 py-3 border-b-4 border-black bg-white z-10 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <h2 className="text-xs font-mono font-black tracking-widest uppercase text-black flex items-center gap-2">
                  <Eye size={16} strokeWidth={2.5} /> LIVE EDITOR & PROVENANCE DIFF
                </h2>
                {isFetchingText && <Loader2 size={14} className="animate-spin text-black" />}
              </div>
              <div className="flex items-center gap-2 text-[10px] font-mono font-bold uppercase text-gray-600 bg-[#FAF8F5] border border-black px-2.5 py-1">
                <span>{activeConflict ? 'BASELINE_DIFF_VIEW' : 'CURRENT_CANVAS_VIEW'}</span>
              </div>
            </header>
            
            {/* Canvas */}
            <div className="flex-grow p-4 sm:p-8 overflow-y-auto overflow-x-hidden pb-72 brutalist-scrollbar bg-[radial-gradient(#00000025_1px,transparent_1px)] [background-size:20px_20px]">
              <div className="bg-white border-4 border-black shadow-[10px_10px_0px_0px_rgba(0,0,0,1)] w-full max-w-5xl mx-auto p-6 sm:p-10 font-mono text-[13px] leading-relaxed break-words whitespace-pre-wrap text-black relative">
                <div className="absolute top-3 right-4 text-[9px] font-mono font-bold uppercase text-gray-400 select-none">
                  {activeConflict ? 'TARGET_DIFF_PROVENANCE' : 'ACTIVE_CANVAS'}
                </div>
                {renderInlineDiffDocument()}
              </div>
            </div>

            {/* DOCKED HUMAN GATE COMMAND CENTER */}
            {activeConflict && (
              <div className="absolute bottom-6 left-1/2 -translate-x-1/2 w-[92%] max-w-4xl bg-white border-4 border-black shadow-[14px_14px_0px_0px_rgba(0,0,0,1)] p-6 flex flex-col gap-5 z-30 animate-in slide-in-from-bottom-6 duration-200">
                
                <div className="flex items-center justify-between border-b-2 border-black pb-3">
                  <div className="flex items-center gap-3">
                    <span className="text-[10px] font-mono font-black text-black bg-[#E9FF70] border-2 border-black px-2.5 py-1 uppercase tracking-widest shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
                      AI REASONING
                    </span>
                    <span className="text-sm font-black text-black uppercase tracking-tight">
                      {activeConflict.topic}
                    </span>
                  </div>
                  <span className="text-[10px] font-mono bg-black text-white px-2.5 py-1 font-bold uppercase tracking-wider">
                    HUMAN APPROVAL GATE REQUIRED
                  </span>
                </div>

                <p className="text-xs text-black font-mono font-bold leading-relaxed bg-[#FAF8F5] p-3.5 border-2 border-black shadow-inner break-words">
                  {activeConflict.ai_reasoning}
                </p>
                
                <div className="grid grid-cols-2 gap-4">
                  <button 
                    onClick={() => resolveConflict(activeConflict.id, 'RESOLVED_KEPT_B')} 
                    className="bg-[#00E599] hover:bg-[#00FFaa] text-black border-2 border-black font-black text-xs uppercase tracking-widest py-3.5 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] hover:translate-y-[2px] hover:translate-x-[2px] hover:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] active:translate-y-[4px] active:translate-x-[4px] active:shadow-none transition-all flex items-center justify-center gap-2"
                  >
                    <Check size={18} strokeWidth={3} />
                    <span>OVERRIDE ORIGINAL</span>
                    <span className="ml-1 text-[9px] bg-black text-white px-1.5 py-0.5 font-mono font-normal">[O]</span>
                  </button>
                  <button 
                    onClick={() => resolveConflict(activeConflict.id, 'RESOLVED_KEPT_A')} 
                    className="bg-[#FF2E5B] hover:bg-[#ff1749] text-white border-2 border-black font-black text-xs uppercase tracking-widest py-3.5 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] hover:translate-y-[2px] hover:translate-x-[2px] hover:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] active:translate-y-[4px] active:translate-x-[4px] active:shadow-none transition-all flex items-center justify-center gap-2"
                  >
                    <X size={18} strokeWidth={3} />
                    <span>REJECT OVERRIDE (RETAIN ORIGINAL)</span>
                    <span className="ml-1 text-[9px] bg-white text-black px-1.5 py-0.5 font-mono font-normal">[R]</span>
                  </button>
                </div>
              </div>
            )}
          </section>
          
        </main>
      </div>
    </>
  );
}