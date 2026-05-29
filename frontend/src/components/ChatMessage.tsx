import { useState } from "react";
import { ChevronDown, ChevronUp, Bot, User, AlertTriangle } from "lucide-react";
import type { Message, Source } from "../api";

interface Props {
  message: Message;
}

const LOW_CONFIDENCE_THRESHOLD = 0.40;

/** Extract the sentence in *answer* that contains the citation for this source. */
function extractCitedSentence(answer: string, src: Source): string | null {
  if (!src.page_number || !src.document_name) return null;
  const citation = `[Page ${src.page_number}, ${src.document_name}]`;
  const idx = answer.indexOf(citation);
  if (idx === -1) return null;

  // Walk backwards to the previous sentence-ending punctuation
  let sentStart = idx;
  for (let i = idx - 1; i >= 0; i--) {
    if (['.', '!', '?', '\n'].includes(answer[i])) {
      sentStart = i + 1;
      break;
    }
    if (i === 0) sentStart = 0;
  }

  // Walk forwards to the next sentence-ending punctuation after the citation
  let sentEnd = answer.length;
  for (let i = idx + citation.length; i < answer.length; i++) {
    if (['.', '!', '?', '\n'].includes(answer[i])) {
      sentEnd = i + 1;
      break;
    }
  }

  return answer.slice(sentStart, sentEnd).trim() || null;
}

function SourceCard({ src, answer }: { src: Source; answer: string }) {
  const citedSentence = extractCitedSentence(answer, src);
  const label = src.document_name
    ? `${src.document_name}${src.page_number != null ? ` · Page ${src.page_number}` : ""}`
    : `Chunk ${src.chunk_index + 1}`;

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium text-sky-400 truncate max-w-[75%]">{label}</span>
        <span className="text-xs text-gray-500 shrink-0">score: {src.score.toFixed(3)}</span>
      </div>
      {citedSentence && (
        <p className="text-xs text-yellow-300 leading-relaxed mb-1 italic">
          &ldquo;{citedSentence}&rdquo;
        </p>
      )}
      <p className="text-xs text-gray-400 leading-relaxed line-clamp-4">{src.content}</p>
    </div>
  );
}

export function ChatMessage({ message }: Props) {
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const isUser = message.role === "user";

  const maxScore = message.sources?.length
    ? Math.max(...message.sources.map(s => s.score))
    : 1;
  const lowConfidence = !isUser && !!message.sources?.length && maxScore < LOW_CONFIDENCE_THRESHOLD;

  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}>
      <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-0.5 ${isUser ? "bg-sky-600" : "bg-gray-700"}`}>
        {isUser ? <User size={14} /> : <Bot size={14} />}
      </div>

      <div className={`max-w-[80%] space-y-2 ${isUser ? "items-end" : "items-start"} flex flex-col`}>
        <div className={`px-4 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${isUser ? "bg-sky-600 text-white rounded-tr-sm" : "bg-gray-800 text-gray-100 rounded-tl-sm"}`}>
          {message.content}
        </div>

        {lowConfidence && (
          <div className="flex items-center gap-1.5 text-xs text-yellow-400">
            <AlertTriangle size={12} />
            Low confidence — document may not cover this topic
          </div>
        )}

        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="w-full">
            <button
              onClick={() => setSourcesOpen(o => !o)}
              className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-300 transition-colors"
            >
              {sourcesOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              {message.sources.length} source{message.sources.length > 1 ? "s" : ""}
            </button>
            {sourcesOpen && (
              <div className="mt-1.5 space-y-1.5">
                {message.sources.map((src, i) => (
                  <SourceCard key={i} src={src} answer={message.content} />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
