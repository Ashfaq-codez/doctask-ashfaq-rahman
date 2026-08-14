import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Upload, AlertCircle, FileText, Check, X, Database, ShieldAlert, ChevronDown, ChevronRight, Eye, FileSearch, Loader2 } from 'lucide-react';

interface Conflict {
  id: string;
  run_id: string;
  topic: string;
  ai_reasoning: string;
  status: string;
  fact_a_text?: string;
  fact_b_text?: string;
  document_id?: string;
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

const API_BASE_URL = 'http://127.0.0.1:8000/api/v1';

export default function App() {
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [facts, setFacts] = useState<Fact[]>([]);
  const [currentDocumentText, setCurrentDocumentText] = useState<string>("SELECT A PENDING REVIEW TO LOAD DOCUMENT CONTEXT.");
  
  const [file, setFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isFetchingText, setIsFetchingText] = useState(false);
  
  const [factsExpanded, setFactsExpanded] = useState(true);
  const [activeConflict, setActiveConflict] = useState<Conflict | null>(null);

  const fetchData = async () => {
    try {
      const [conflictsRes, factsRes] = await Promise.all([
        axios.get(`${API_BASE_URL}/conflicts/pending`),
        axios.get(`${API_BASE_URL}/facts/`)
      ]);
      setConflicts(conflictsRes.data || []);
      setFacts(factsRes.data || []);
      
      if (activeConflict && !(conflictsRes.data || []).find((c: Conflict) => c.id === activeConflict.id)) {
        setActiveConflict(null);
      }
    } catch (error) {
      console.error("Failed to fetch data:", error);
    }
  };

  useEffect(() => {
    fetchData(); 
    const interval = setInterval(() => {
      fetchData();
    }, 2500);
    return () => clearInterval(interval);
  }, []); 

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setIsProcessing(true);
    
    const reader = new FileReader();
    reader.onload = (event) => {
      if (event.target?.result) {
        setCurrentDocumentText(event.target.result as string);
        setActiveConflict(null);
      }
    };
    reader.readAsText(file);

    const formData = new FormData();
    formData.append('file', file);

    try {
      await axios.post(`${API_BASE_URL}/upload/`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setFile(null);
      setTimeout(() => setIsProcessing(false), 3000);
    } catch (error) {
      console.error("Upload failed:", error);
      setCurrentDocumentText("FATAL ERROR: UPLOAD FAILED.");
      setIsProcessing(false);
    }
  };

  const handleConflictClick = async (conflict: Conflict) => {
    setActiveConflict(conflict);
    if (!conflict.document_id) return;
    
    setIsFetchingText(true);
    try {
      const response = await axios.get(`${API_BASE_URL}/conflicts/document-text/${conflict.document_id}`);
      setCurrentDocumentText(response.data.text);
    } catch (error) {
      console.error("Failed to fetch document text:", error);
      setCurrentDocumentText("ERROR: SOURCE DOCUMENT UNAVAILABLE.");
    }
    setIsFetchingText(false);
  };

  const resolveConflict = async (conflictId: string, resolutionStatus: string) => {
    try {
      await axios.post(`${API_BASE_URL}/conflicts/${conflictId}/resolve`, {
        status: resolutionStatus
      });
      setConflicts(conflicts.filter(c => c.id !== conflictId));
      if (activeConflict?.id === conflictId) {
        setActiveConflict(null);
      }
    } catch (error) {
      console.error("Resolution failed:", error);
    }
  };

  const renderInlineDiffDocument = () => {
    if (!activeConflict || !activeConflict.fact_b_text || !activeConflict.fact_a_text) {
      return currentDocumentText;
    }
    
    const newText = activeConflict.fact_b_text;
    const oldText = activeConflict.fact_a_text;

    if (!currentDocumentText || !currentDocumentText.includes(newText)) {
      return currentDocumentText;
    }

    const parts = currentDocumentText.split(newText);
    
    return (
      <>
        {parts.map((part, i) => (
          <React.Fragment key={i}>
            {part}
            {i < parts.length - 1 && (
              <span className="inline-flex items-center align-middle mx-1 whitespace-normal text-black font-bold">
                <del className="bg-[#FF4A4A] px-2 py-0.5 border-2 border-black border-r-0 decoration-black decoration-2 line-through">
                  {oldText}
                </del>
                <ins className="bg-[#00E599] px-2 py-0.5 border-2 border-black no-underline">
                  {newText}
                </ins>
              </span>
            )}
          </React.Fragment>
        ))}
      </>
    );
  };

  return (
    <>
      {/* Import stark neo-grotesque typography */}
      <style dangerouslySetInnerHTML={{__html: `
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700;900&display=swap');
        
        .brutalist-scrollbar::-webkit-scrollbar { width: 12px; }
        .brutalist-scrollbar::-webkit-scrollbar-track { background: #F0F0EE; border-left: 2px solid black; }
        .brutalist-scrollbar::-webkit-scrollbar-thumb { background-color: black; border: 2px solid #F0F0EE; }
      `}} />

      <div className="min-h-screen bg-[#F0F0EE] text-black font-['Space_Grotesk',sans-serif] selection:bg-[#FFCC00] selection:text-black flex flex-col relative overflow-hidden">
        
        {/* RAW BRUTALIST LOADING OVERLAY */}
        {isProcessing && (
          <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-[#FFCC00] border-8 border-black transition-all duration-0">
            <div className="bg-white border-4 border-black shadow-[12px_12px_0px_0px_rgba(0,0,0,1)] p-12 max-w-lg w-full flex flex-col items-center text-center">
              <img 
                src="/loading.gif" 
                alt="Processing..." 
                className="object-cover mb-8 border-4 border-black "
                onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
              />
              <h2 className="text-5xl font-black uppercase tracking-tighter mb-4 text-black">Auditing</h2>
              <p className="text-lg font-bold text-black border-2 border-black bg-[#E9FF70] px-4 py-2 inline-flex items-center gap-2 uppercase">
                <FileSearch size={20} strokeWidth={3} />
                Enforcing Memory Checks
              </p>
            </div>
          </div>
        )}

        {/* STARK HEADER */}
        <header className="bg-white border-b-4 border-black px-8 py-4 flex items-center justify-between z-10 sticky top-0">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 bg-[#FF3366] border-2 border-black flex items-center justify-center shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]">
              <ShieldAlert size={20} className="text-black" strokeWidth={2.5} />
            </div>
            <h1 className="text-xl font-black uppercase tracking-tighter text-black">DocTask<span className="text-[#FF3366]">.Agent</span></h1>
          </div>
          
          <div className="flex items-center gap-2 bg-[#00E599] border-2 border-black text-black px-4 py-1.5 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]">
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-black opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-black"></span>
            </span>
            <span className="text-xs font-black uppercase tracking-widest">Live Sync</span>
          </div>
        </header>

        <main className="flex-grow flex flex-col lg:flex-row h-[calc(100vh-76px)]">
          
          {/* --- LEFT SIDEBAR: Solid blocks, hard shadows --- */}
          <aside className="w-full lg:w-[480px] bg-white border-r-4 border-black flex flex-col h-full overflow-y-auto brutalist-scrollbar z-10">
            <div className="p-8 space-y-10">
              
              {/* Ingestion Dropzone */}
              <section className="space-y-4">
                <h2 className="text-sm font-black uppercase tracking-widest text-black flex items-center gap-2 border-b-2 border-black pb-2">
                  <Upload size={18} strokeWidth={2.5} /> Data Ingestion
                </h2>
                <form onSubmit={handleUpload} className="space-y-4">
                  <label className="flex flex-col items-center justify-center w-full h-20 transition-all bg-[#F9F9F9] border-2 border-dashed border-black hover:bg-[#E9FF70] cursor-pointer group">
                    <span className="flex items-center gap-3 text-sm text-black font-bold w-full px-5">
                      <FileText size={20} strokeWidth={2.5} className="flex-shrink-0" />
                      <span className="truncate uppercase">{file ? file.name : "SELECT SOURCE FILE"}</span>
                    </span>
                    <input type="file" className="hidden" onChange={(e) => setFile(e.target.files?.[0] || null)}/>
                  </label>
                  <button type="submit" disabled={!file || isProcessing} className="w-full bg-[#FFCC00] text-black border-2 border-black text-sm font-black uppercase tracking-widest py-4 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] hover:translate-y-[2px] hover:translate-x-[2px] hover:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] active:translate-y-[4px] active:translate-x-[4px] active:shadow-none disabled:opacity-50 disabled:pointer-events-none transition-all">
                    Execute Audit
                  </button>
                </form>
              </section>

              {/* Verified Facts */}
              <section className="space-y-4">
                <button onClick={() => setFactsExpanded(!factsExpanded)} className="w-full flex items-center justify-between text-black border-b-2 border-black pb-2 hover:bg-[#F0F0EE] transition-colors">
                  <h2 className="text-sm font-black uppercase tracking-widest flex items-center gap-2">
                    <Database size={18} strokeWidth={2.5} /> Verified Facts ({facts.length})
                  </h2>
                  {factsExpanded ? <ChevronDown size={20} strokeWidth={2.5} /> : <ChevronRight size={20} strokeWidth={2.5} />}
                </button>
                
                {factsExpanded && (
                  <div className="bg-[#F9F9F9] border-2 border-black flex-grow p-4 max-h-[250px] overflow-y-auto brutalist-scrollbar shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
                    {facts.length === 0 ? (
                      <div className="text-xs font-bold uppercase tracking-widest text-center py-6 text-black">Awaiting Data</div>
                    ) : (
                      <ul className="space-y-4">
                        {facts.map((fact) => (
                          <li key={fact.id} className="p-4 bg-white border-2 border-black shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
                            <span className="block font-black text-black uppercase tracking-widest text-[10px] bg-[#E9FF70] border-b-2 border-black -mx-4 -mt-4 mb-3 px-4 py-1.5">
                              {fact.key?.replace(/_/g, ' ') || 'EXTRACTED FACT'}
                            </span>
                            <span className="block font-bold text-black mb-3 leading-snug">{fact.value || 'No value'}</span>
                            <div className="flex items-center gap-2 text-[10px] font-black uppercase text-black bg-[#F0F0EE] border-2 border-black px-2 py-1 w-fit">
                              <FileText size={12} strokeWidth={2.5} />
                              <span className="truncate max-w-[200px]">{fact.document_name || "RECORD"}</span>
                            </div>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </section>

              {/* Review Gate */}
              <section className="pb-8 space-y-4">
                <header className="flex items-center justify-between border-b-2 border-black pb-2">
                  <h2 className="text-sm font-black uppercase tracking-widest text-black flex items-center gap-2">
                    <AlertCircle size={18} strokeWidth={2.5} /> Review Gate
                  </h2>
                  <span className={`text-[10px] font-black tracking-widest px-3 py-1 uppercase border-2 border-black shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] ${conflicts.length > 0 ? 'bg-[#FF3366] text-white' : 'bg-[#00E599] text-black'}`}>
                    {conflicts.length} Pending
                  </span>
                </header>

                {conflicts.length === 0 ? (
                  <div className="bg-white border-2 border-black border-dashed p-8 flex flex-col items-center justify-center text-center">
                    <Check size={32} className="text-black bg-[#00E599] border-2 border-black p-1.5 mb-4 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]" strokeWidth={3} />
                    <p className="text-sm font-black tracking-widest text-black uppercase">System Clear</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {conflicts.map((conflict) => (
                      <article 
                        key={conflict.id} 
                        onClick={() => handleConflictClick(conflict)}
                        className={`border-2 border-black p-5 cursor-pointer transition-all shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]
                          ${activeConflict?.id === conflict.id ? 'bg-[#FFCC00] translate-x-[2px] translate-y-[2px] shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]' : 'bg-white hover:bg-[#F9F9F9]'}`}
                      >
                        <h3 className="text-sm font-black text-black mb-2 uppercase leading-tight">{conflict.topic}</h3>
                        <p className="text-xs text-black font-medium leading-relaxed font-mono">{conflict.ai_reasoning}</p>
                      </article>
                    ))}
                  </div>
                )}
              </section>
            </div>
          </aside>

          {/* --- RIGHT MAIN SECTION: Document Viewer --- */}
          <section className="flex-grow flex flex-col bg-[#F0F0EE] relative overflow-hidden">
            <header className="px-8 py-4 border-b-4 border-black bg-white z-10 flex items-center justify-between">
              <h2 className="text-sm font-black tracking-widest uppercase text-black flex items-center gap-3">
                <Eye size={18} strokeWidth={2.5} /> Editor View
                {isFetchingText && <Loader2 size={16} className="animate-spin text-black" />}
              </h2>
            </header>
            
            {/* Document Content */}
            <div className="flex-grow p-8 overflow-y-auto pb-72 brutalist-scrollbar bg-[radial-gradient(#00000022_1px,transparent_1px)] [background-size:16px_16px]">
              <div className="bg-white border-4 border-black shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] w-full min-h-full p-12 font-mono text-[14px] leading-loose whitespace-pre-wrap text-black max-w-5xl mx-auto">
                {renderInlineDiffDocument()}
              </div>
            </div>

            {/* DOCKED COMMAND CENTER */}
            {activeConflict && (
              <div className="absolute bottom-8 left-1/2 -translate-x-1/2 w-[95%] max-w-4xl bg-white border-4 border-black shadow-[12px_12px_0px_0px_rgba(0,0,0,1)] p-8 flex flex-col gap-6 z-20 transition-transform">
                <div>
                  <div className="flex items-center gap-3 mb-4 border-b-2 border-black pb-3">
                    <span className="text-[10px] font-black text-black bg-[#E9FF70] border-2 border-black px-3 py-1 uppercase tracking-widest shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">Reasoning</span>
                    <span className="text-sm font-black text-black uppercase truncate">{activeConflict.topic}</span>
                  </div>
                  <p className="text-sm text-black font-mono font-bold leading-relaxed bg-[#F9F9F9] p-4 border-2 border-black">{activeConflict.ai_reasoning}</p>
                </div>
                
                <div className="flex gap-6">
                  <button 
                    onClick={() => resolveConflict(activeConflict.id, 'resolved_manual_edit')} 
                    className="flex-1 bg-[#00E599] text-black border-2 border-black font-black text-sm uppercase tracking-widest py-4 hover:bg-white shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] hover:translate-y-[2px] hover:translate-x-[2px] hover:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] active:translate-y-[4px] active:translate-x-[4px] active:shadow-none transition-all flex items-center justify-center gap-3"
                  >
                    <Check size={20} strokeWidth={3} /> Override Original
                  </button>
                  <button 
                    onClick={() => resolveConflict(activeConflict.id, 'resolved_kept_a')} 
                    className="flex-1 bg-[#FF3366] text-white border-2 border-black font-black text-sm uppercase tracking-widest py-4 hover:bg-black shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] hover:translate-y-[2px] hover:translate-x-[2px] hover:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] active:translate-y-[4px] active:translate-x-[4px] active:shadow-none transition-all flex items-center justify-center gap-3"
                  >
                    <X size={20} strokeWidth={3} /> Reject Override
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