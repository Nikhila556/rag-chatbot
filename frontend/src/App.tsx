import { useState } from "react";
import { Sidebar } from "./components/Sidebar";
import { ChatPanel } from "./components/ChatPanel";
import { UploadZone } from "./components/UploadZone";
import "./index.css";

export default function App() {
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const refresh = () => setRefreshTrigger(n => n + 1);

  return (
    <div className="flex h-screen bg-gray-950 text-gray-100 overflow-hidden">
      <div className="flex flex-col w-64 shrink-0 h-screen">
        <Sidebar
          activeConversationId={activeConversationId}
          onSelectConversation={(id, docId) => {
            setActiveConversationId(id);
            setSelectedDocumentId(docId ?? null);
          }}
          onNewChat={() => setActiveConversationId(null)}
          onDocumentSelect={id => {
            if (id !== selectedDocumentId) {
              setActiveConversationId(null);
            }
            setSelectedDocumentId(id);
          }}
          selectedDocumentId={selectedDocumentId}
          refreshTrigger={refreshTrigger}
        />
        <UploadZone onUploaded={refresh} />
      </div>

      <main className="flex-1 flex flex-col min-w-0">
        <div className="px-6 py-3 border-b border-gray-800 flex items-center gap-2">
          <h2 className="text-sm font-medium text-gray-300">
            {selectedDocumentId ? "Document Q&A" : "All Documents"}
          </h2>
        </div>
        <div className="flex-1 overflow-hidden min-h-0">
          <ChatPanel
            conversationId={activeConversationId}
            documentId={selectedDocumentId}
            onConversationCreated={id => { setActiveConversationId(id); refresh(); }}
            onMessagesChanged={refresh}
          />
        </div>
      </main>
    </div>
  );
}
