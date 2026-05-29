import { useEffect, useState } from "react";
import { MessageSquare, Trash2, Plus, FileText, ChevronDown, ChevronUp } from "lucide-react";
import { listConversations, deleteConversation, listDocuments, deleteDocument, type Conversation, type Document } from "../api";

interface Props {
  activeConversationId: string | null;
  onSelectConversation: (id: string, documentId: string | null) => void;
  onNewChat: () => void;
  onDocumentSelect: (id: string | null) => void;
  selectedDocumentId: string | null;
  refreshTrigger: number;
}

export function Sidebar({ activeConversationId, onSelectConversation, onNewChat, onDocumentSelect, selectedDocumentId, refreshTrigger }: Props) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [docsOpen, setDocsOpen] = useState(true);

  const loadAll = async () => {
    const [convRes, docRes] = await Promise.all([listConversations(), listDocuments()]);
    setConversations(convRes.data);
    setDocuments(docRes.data);
  };

  useEffect(() => { loadAll(); }, [refreshTrigger]);

  const handleDeleteConv = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    await deleteConversation(id);
    setConversations(prev => prev.filter(c => c.id !== id));
  };

  const handleDeleteDoc = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    await deleteDocument(id);
    setDocuments(prev => prev.filter(d => d.id !== id));
    if (selectedDocumentId === id) onDocumentSelect(null);
  };

  return (
    <aside className="w-64 bg-gray-900 border-r border-gray-800 flex flex-col flex-1 min-h-0">
      <div className="p-4 border-b border-gray-800 shrink-0">
        <h1 className="text-lg font-semibold text-white">RAG Chat</h1>
        <p className="text-xs text-gray-400 mt-0.5">Document Q&amp;A</p>
      </div>

      <button
        onClick={onNewChat}
        className="mx-3 mt-3 flex items-center gap-2 px-3 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-sm font-medium transition-colors shrink-0"
      >
        <Plus size={15} /> New Chat
      </button>

      {/* Documents section */}
      <div className="mt-4 px-3 shrink-0">
        <button
          onClick={() => setDocsOpen(o => !o)}
          className="flex items-center justify-between w-full text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1"
        >
          Documents {docsOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </button>
        {docsOpen && (
          <ul className="space-y-0.5">
            <li>
              <button
                onClick={() => onDocumentSelect(null)}
                className={`w-full text-left flex items-center gap-2 px-2 py-1.5 rounded-md text-sm transition-colors ${selectedDocumentId === null ? "bg-gray-700 text-white" : "text-gray-400 hover:bg-gray-800 hover:text-white"}`}
              >
                <FileText size={13} /> All documents
              </button>
            </li>
            {documents.map(doc => (
              <li key={doc.id}>
                <button
                  onClick={() => onDocumentSelect(doc.id)}
                  className={`w-full text-left flex items-center gap-2 px-2 py-1.5 rounded-md text-sm transition-colors group ${selectedDocumentId === doc.id ? "bg-gray-700 text-white" : "text-gray-400 hover:bg-gray-800 hover:text-white"}`}
                >
                  <FileText size={13} className="shrink-0" />
                  <span className="truncate flex-1">{doc.filename}</span>
                  <button
                    onClick={e => handleDeleteDoc(e, doc.id)}
                    className="opacity-0 group-hover:opacity-100 text-gray-500 hover:text-red-400 transition"
                  >
                    <Trash2 size={12} />
                  </button>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Conversations section */}
      <div className="mt-4 px-3 flex-1 overflow-y-auto min-h-0">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Chats</p>
        <ul className="space-y-0.5">
          {conversations.map(conv => (
            <li key={conv.id}>
              <button
                onClick={() => onSelectConversation(conv.id, conv.document_id)}
                className={`w-full text-left flex items-center gap-2 px-2 py-1.5 rounded-md text-sm transition-colors group ${activeConversationId === conv.id ? "bg-gray-700 text-white" : "text-gray-400 hover:bg-gray-800 hover:text-white"}`}
              >
                <MessageSquare size={13} className="shrink-0" />
                <span className="truncate flex-1">{conv.title}</span>
                <button
                  onClick={e => handleDeleteConv(e, conv.id)}
                  className="opacity-0 group-hover:opacity-100 text-gray-500 hover:text-red-400 transition"
                >
                  <Trash2 size={12} />
                </button>
              </button>
            </li>
          ))}
          {conversations.length === 0 && (
            <li className="text-xs text-gray-600 px-2 py-2">No chats yet</li>
          )}
        </ul>
      </div>
    </aside>
  );
}
