import { useEffect, useRef, useState } from "react";
import { Send, Loader2, FileText } from "lucide-react";
import { streamChat, getMessages, type Message, type Source } from "../api";
import { ChatMessage } from "./ChatMessage";

interface Props {
  conversationId: string | null;
  documentId: string | null;
  onConversationCreated: (id: string) => void;
  onMessagesChanged: () => void;
}

export function ChatPanel({ conversationId, documentId, onConversationCreated, onMessagesChanged }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // True while a stream is in flight; tracks which conv is being streamed.
  const streamingRef = useRef(false);
  const streamingConvRef = useRef<string | null>(null);

  useEffect(() => {
    if (!conversationId) {
      setMessages([]);
      return;
    }
    getMessages(conversationId)
      .then(res => {
        // If this exact conversation is actively streaming, messages are already
        // correct in local state — skip the DB snapshot to avoid overwriting
        // the in-progress assistant message with an incomplete version.
        if (streamingRef.current && streamingConvRef.current === conversationId) return;
        setMessages(res.data.messages);
      })
      .catch(() => {});
  }, [conversationId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const submit = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setError(null);

    const userMsgId = crypto.randomUUID();
    const assistantMsgId = crypto.randomUUID();

    setMessages(prev => [
      ...prev,
      { id: userMsgId, role: "user", content: text, created_at: new Date().toISOString() },
      { id: assistantMsgId, role: "assistant", content: "", created_at: new Date().toISOString() },
    ]);
    setLoading(true);
    streamingRef.current = true;

    try {
      const gen = streamChat({
        conversation_id: conversationId ?? undefined,
        document_id: documentId ?? undefined,
        message: text,
      });

      let convCreated = false;

      for await (const event of gen) {
        if (event.type === "meta") {
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantMsgId ? { ...m, sources: event.sources as Source[] } : m
            )
          );
          if (!conversationId && !convCreated) {
            convCreated = true;
            // Mark the conversation being streamed BEFORE triggering the prop
            // change so the useEffect guard is in place when it fires.
            streamingConvRef.current = event.conversation_id;
            onConversationCreated(event.conversation_id);
            onMessagesChanged();
          }
        } else if (event.type === "token") {
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantMsgId ? { ...m, content: m.content + event.content } : m
            )
          );
        } else if (event.type === "error") {
          setError(event.message);
          setMessages(prev => prev.filter(m => m.id !== assistantMsgId));
        }
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Something went wrong";
      setError(msg);
      setMessages(prev => prev.filter(m => m.id !== assistantMsgId));
    } finally {
      streamingRef.current = false;
      setLoading(false);
    }
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); }
  };

  const isStreaming = loading && messages.at(-1)?.role === "assistant" && messages.at(-1)?.content === "";

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto min-h-0 px-6 py-6 space-y-5">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
            <FileText size={40} className="text-gray-700" />
            <p className="text-gray-500 text-sm max-w-sm">
              {documentId
                ? "Ask a question about the selected document."
                : "Select a document from the sidebar or upload one, then ask a question."}
            </p>
          </div>
        )}
        {messages.map(msg => <ChatMessage key={msg.id} message={msg} />)}
        {isStreaming && (
          <div className="flex gap-3">
            <div className="w-7 h-7 rounded-full bg-gray-700 flex items-center justify-center">
              <Loader2 size={14} className="animate-spin" />
            </div>
            <div className="bg-gray-800 rounded-2xl rounded-tl-sm px-4 py-2.5 text-sm text-gray-400">
              Thinking…
            </div>
          </div>
        )}
        {error && <p className="text-xs text-red-400 text-center">{error}</p>}
        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div className="px-6 py-4 border-t border-gray-800 shrink-0">
        <div className="flex items-end gap-2 bg-gray-800 rounded-2xl px-4 py-2 border border-gray-700 focus-within:border-sky-500 transition-colors">
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Ask a question…"
            rows={1}
            className="flex-1 bg-transparent text-sm text-gray-100 placeholder-gray-500 resize-none outline-none min-h-[24px] max-h-32 py-0.5"
            style={{ height: "auto" }}
            onInput={e => {
              const t = e.target as HTMLTextAreaElement;
              t.style.height = "auto";
              t.style.height = t.scrollHeight + "px";
            }}
          />
          <button
            onClick={submit}
            disabled={!input.trim() || loading}
            className="text-sky-400 hover:text-sky-300 disabled:text-gray-600 transition-colors pb-0.5"
          >
            <Send size={17} />
          </button>
        </div>
        <p className="text-xs text-gray-600 mt-1.5 text-center">Shift+Enter for newline · Enter to send</p>
      </div>
    </div>
  );
}
