import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Upload, AlertCircle, RefreshCw, FileText, Check, X } from 'lucide-react';

interface Conflict {
  id: string;
  run_id: string;
  topic: string;
  ai_reasoning: string;
  status: string;
}

interface Fact {
  id: string;
  document_id: string;
  key: string;
  value: string;
}

const API_BASE_URL = 'http://127.0.0.1:8000/api/v1';

export default function App() {
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [facts, setFacts] = useState<Fact[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const fetchData = async () => {
    setIsRefreshing(true);
    try {
      const [conflictsRes, factsRes] = await Promise.all([
        axios.get(`${API_BASE_URL}/conflicts/pending`),
        axios.get(`${API_BASE_URL}/facts/`)
      ]);
      setConflicts(conflictsRes.data);
      setFacts(factsRes.data);
    } catch (error) {
      console.error("Failed to fetch data:", error);
    }
    setIsRefreshing(false);
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setIsUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      await axios.post(`${API_BASE_URL}/upload/`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setFile(null);
      setTimeout(fetchData, 3000);
    } catch (error) {
      console.error("Upload failed:", error);
    }
    setIsUploading(false);
  };

  const resolveConflict = async (conflictId: string, resolutionStatus: string) => {
    try {
      await axios.post(`${API_BASE_URL}/conflicts/${conflictId}/resolve`, {
        status: resolutionStatus
      });
      setConflicts(conflicts.filter(c => c.id !== conflictId));
    } catch (error) {
      console.error("Resolution failed:", error);
    }
  };

  return (
    <div className="min-h-screen bg-[#FAFAFA] text-gray-900 font-sans selection:bg-gray-200">
      
      {/* Navigation / Header */}
      <header className="sticky top-0 z-10 bg-white/80 backdrop-blur-md border-b border-gray-200 px-6 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-medium tracking-tight text-black">SuperDocs</h1>
          <p className="text-xs text-gray-500 tracking-wide mt-0.5 uppercase">Agentic Processing Pipeline</p>
        </div>
        <button 
          onClick={fetchData}
          className="text-xs uppercase tracking-widest text-gray-500 hover:text-black transition-colors flex items-center gap-2 w-fit"
        >
          <RefreshCw size={14} className={isRefreshing ? "animate-spin" : ""} />
          Sync State
        </button>
      </header>

      {/* Main Layout Grid */}
      <main className="max-w-7xl mx-auto px-6 py-12 grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-16">
        
        {/* Left Column: Input & Data */}
        <div className="lg:col-span-4 space-y-12">
          
          {/* Document Ingestion */}
          <section>
            <h2 className="text-sm font-medium tracking-wide uppercase text-gray-500 mb-4 flex items-center gap-2">
              <Upload size={16} /> Data Ingestion
            </h2>
            <form onSubmit={handleUpload} className="space-y-4">
              <label className="flex flex-col items-center justify-center w-full h-32 px-4 transition bg-white border border-gray-300 border-dashed hover:bg-gray-50 cursor-pointer">
                <span className="flex items-center space-x-2 text-sm text-gray-500">
                  <FileText size={18} />
                  <span className="font-medium text-gray-900">
                    {file ? file.name : "Select document"}
                  </span>
                </span>
                <input 
                  type="file" 
                  name="file_upload" 
                  className="hidden" 
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                />
              </label>
              
              <button 
                type="submit" 
                disabled={!file || isUploading}
                className="w-full bg-black text-white text-sm font-medium py-3 hover:bg-gray-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                {isUploading ? "Processing Sequence..." : "Initialize Run"}
              </button>
            </form>
          </section>

          {/* Extracted Facts Vault */}
          <section>
            <h2 className="text-sm font-medium tracking-wide uppercase text-gray-500 mb-4">
              Validated Telemetry
            </h2>
            <div className="bg-white border border-gray-200">
              <div className="max-h-[500px] overflow-y-auto">
                {facts.length === 0 ? (
                  <p className="text-sm text-gray-400 p-6 text-center">Awaiting data extraction.</p>
                ) : (
                  <ul className="divide-y divide-gray-100">
                    {facts.map((fact) => (
                      <li key={fact.id} className="p-4 hover:bg-gray-50 transition-colors">
                        <span className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">
                          {fact.key.replace(/_/g, ' ')}
                        </span>
                        <span className="block text-sm text-gray-800 leading-relaxed">
                          {fact.value}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </section>
        </div>

        {/* Right Column: Auditor Queue */}
        <div className="lg:col-span-8">
          <section>
            <header className="flex items-center justify-between mb-6">
              <h2 className="text-sm font-medium tracking-wide uppercase text-gray-500 flex items-center gap-2">
                <AlertCircle size={16} /> Human Review Gate
              </h2>
              <span className="text-xs font-medium bg-gray-200 text-gray-700 px-2 py-1 rounded-full">
                {conflicts.length} Pending
              </span>
            </header>

            {conflicts.length === 0 ? (
              <div className="bg-white border border-gray-200 p-12 flex flex-col items-center justify-center text-center text-gray-400">
                <Check size={32} className="mb-3 text-gray-300" />
                <p className="text-sm font-medium">System nominal. No anomalies detected.</p>
              </div>
            ) : (
              <div className="space-y-6">
                {conflicts.map((conflict) => (
                  <article key={conflict.id} className="bg-white border border-gray-200 p-6 transition-shadow hover:shadow-sm">
                    
                    <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-6">
                      <div>
                        <span className="text-xs font-semibold text-red-600 bg-red-50 px-2 py-1 rounded-sm uppercase tracking-wide border border-red-100">
                          Requires Resolution
                        </span>
                        <h3 className="text-lg font-medium text-gray-900 mt-3">{conflict.topic}</h3>
                      </div>
                    </div>
                    
                    <div className="mb-8">
                      <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Agent Reasoning</p>
                      <div className="bg-gray-50 border border-gray-100 p-4 text-sm text-gray-700 leading-relaxed">
                        {conflict.ai_reasoning}
                      </div>
                    </div>

                    <div className="flex flex-col sm:flex-row gap-3 pt-4 border-t border-gray-100">
                      <button 
                        onClick={() => resolveConflict(conflict.id, 'resolved_manual_edit')}
                        className="flex-1 bg-black text-white text-sm font-medium py-2.5 px-4 hover:bg-gray-800 transition-colors flex items-center justify-center gap-2"
                      >
                        <Check size={16} /> Acknowledge & Override
                      </button>
                      <button 
                        onClick={() => resolveConflict(conflict.id, 'resolved_kept_a')}
                        className="flex-1 bg-white text-gray-700 border border-gray-300 text-sm font-medium py-2.5 px-4 hover:bg-gray-50 transition-colors flex items-center justify-center gap-2"
                      >
                        <X size={16} /> Dismiss Exception
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        </div>

      </main>
    </div>
  );
}