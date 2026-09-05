import { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Bot, Loader2, Send, User } from "lucide-react";
import { copilotChat, getCopilotHistory } from "../lib/api";
import type { CopilotMessage } from "../lib/api";

interface CopilotChatProps {
  applicationId: number | null;
}

export function CopilotChat({ applicationId }: CopilotChatProps) {
  const [messages, setMessages] = useState<CopilotMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Load history when application changes
  useEffect(() => {
    if (!applicationId) { setMessages([]); return; }
    getCopilotHistory(applicationId).then(setMessages).catch(() => setMessages([]));
  }, [applicationId]);

  // Auto-scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    const userMsg: CopilotMessage = { role: "user", content: text, created_at: new Date().toISOString() };
    setMessages((prev) => [...prev, userMsg]);
    setBusy(true);
    try {
      const res = await copilotChat(text, applicationId ?? undefined);
      setMessages((prev) => [...prev, { role: "assistant", content: res.reply, created_at: new Date().toISOString() }]);
    } catch (e) {
      setMessages((prev) => [...prev, { role: "assistant", content: "Something went wrong. Please try again.", created_at: new Date().toISOString() }]);
    } finally {
      setBusy(false);
    }
  }, [input, busy, applicationId]);

  return (
    <div className="flex flex-col h-full">
      {/* messages */}
      <div className="flex-1 overflow-y-auto pr-1 space-y-3 min-h-[200px] max-h-[400px]">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center py-8">
            <Bot className="w-8 h-8 text-primary/30 mb-3" />
            <p className="text-primary/40 text-sm">Ask me about this match.</p>
            <p className="text-primary/30 text-xs mt-1">I&apos;ll ground every answer in your Master CV facts.</p>
          </div>
        )}
        <AnimatePresence>
          {messages.map((msg, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex gap-2.5 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              {msg.role === "assistant" && (
                <div className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
                  <Bot className="w-3.5 h-3.5 text-primary" />
                </div>
              )}
              <div
                className={`max-w-[80%] rounded-xl px-3.5 py-2.5 text-xs leading-relaxed ${
                  msg.role === "user"
                    ? "bg-primary text-black"
                    : "bg-primary/10 text-[#E1E0CC]"
                }`}
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>
              </div>
              {msg.role === "user" && (
                <div className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center shrink-0 mt-0.5">
                  <User className="w-3.5 h-3.5 text-primary" />
                </div>
              )}
            </motion.div>
          ))}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>

      {/* input */}
      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-primary/10">
        <input
          type="text"
          className="flex-1 bg-black/40 border border-primary/20 rounded-xl px-3.5 py-2 text-xs text-[#E1E0CC] placeholder:text-primary/30 outline-none focus:border-primary/50 transition-colors"
          placeholder={applicationId ? "Ask about this match…" : "Select an application first…"}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
          disabled={busy || !applicationId}
        />
        <button
          onClick={send}
          disabled={busy || !input.trim() || !applicationId}
          className="w-8 h-8 rounded-xl bg-primary text-black flex items-center justify-center shrink-0 hover:opacity-90 transition-opacity disabled:opacity-40"
          aria-label="Send message"
        >
          {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
        </button>
      </div>
    </div>
  );
}
