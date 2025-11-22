import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { Send, Bot, User, FileText, Loader2, AlertCircle } from 'lucide-react';

function App() {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Bonjour ! Je suis votre assistant RAG. Posez-moi une question sur vos documents.', files: [] }
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage = { role: 'user', content: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      // In production/docker, this URL might need to be relative or configured via ENV
      // For local dev with proxy or CORS, we might need adjustment.
      // Assuming the docker setup will map localhost:8000 to the API.
      const response = await axios.post('http://localhost:8000/query', {
        question: userMessage.content,
        min_score: 0.01
      });

      const data = response.data;
      
      // The API returns { question, answer, files_used }
      const botMessage = {
        role: 'assistant',
        content: data.answer || "Désolé, je n'ai pas pu générer de réponse.",
        files: data.files_used || []
      };

      setMessages(prev => [...prev, botMessage]);
    } catch (error) {
      console.error("Error querying RAG:", error);
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: "Une erreur est survenue lors de la communication avec le serveur.", 
        isError: true 
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-[var(--bg-primary)] text-[var(--text-primary)] font-sans overflow-hidden">
      {/* Header */}
      <header className="glass-panel p-4 flex items-center justify-center sticky top-0 z-10 border-b border-[var(--border-color)]">
        <Bot className="w-6 h-6 mr-2 text-[var(--accent-primary)]" />
        <h1 className="text-xl font-bold bg-gradient-to-r from-[var(--accent-primary)] to-[var(--accent-secondary)] bg-clip-text text-transparent">
          RAG Assistant
        </h1>
      </header>

      {/* Chat Area */}
      <main className="flex-1 overflow-y-auto p-4 md:p-8 space-y-6 max-w-4xl mx-auto w-full">
        {messages.map((msg, index) => (
          <div 
            key={index} 
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-fade-in`}
          >
            <div className={`max-w-[85%] md:max-w-[75%] rounded-2xl p-4 shadow-lg ${
              msg.role === 'user' 
                ? 'bg-[var(--accent-primary)] text-white rounded-br-none' 
                : 'glass-panel text-[var(--text-primary)] rounded-bl-none border border-[var(--border-color)]'
            }`}>
              <div className="flex items-start gap-3">
                {msg.role === 'assistant' && (
                  <div className="p-1.5 bg-[var(--bg-tertiary)] rounded-full shrink-0 mt-1">
                    {msg.isError ? <AlertCircle size={16} className="text-red-400" /> : <Bot size={16} className="text-[var(--accent-secondary)]" />}
                  </div>
                )}
                
                <div className="flex-1 overflow-hidden">
                  <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                  
                  {/* Source Documents */}
                  {msg.files && msg.files.length > 0 && (
                    <div className="mt-4 pt-3 border-t border-[var(--border-color)]">
                      <p className="text-xs font-semibold text-[var(--text-secondary)] mb-2 flex items-center">
                        <FileText size={12} className="mr-1" /> Sources utilisées
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {msg.files.map((file, fIndex) => (
                          <div 
                            key={fIndex}
                            className="text-xs bg-[var(--bg-tertiary)] hover:bg-[var(--bg-secondary)] transition-colors px-2 py-1 rounded border border-[var(--border-color)] flex items-center gap-1"
                            title={`Score: ${file.score}`}
                          >
                            <span className="truncate max-w-[150px]">{file.file_path.split('/').pop() || file.file_path}</span>
                            <span className="opacity-50 text-[10px]">({Math.round(file.score * 100)}%)</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {msg.role === 'user' && (
                   <div className="p-1.5 bg-white/20 rounded-full shrink-0 mt-1">
                     <User size={16} className="text-white" />
                   </div>
                )}
              </div>
            </div>
          </div>
        ))}
        
        {isLoading && (
          <div className="flex justify-start animate-fade-in">
             <div className="glass-panel rounded-2xl rounded-bl-none p-4 flex items-center gap-2">
                <div className="p-1.5 bg-[var(--bg-tertiary)] rounded-full">
                  <Bot size={16} className="text-[var(--accent-secondary)]" />
                </div>
                <div className="flex gap-1 h-4 items-center px-2">
                  <div className="w-2 h-2 bg-[var(--text-secondary)] rounded-full typing-dot"></div>
                  <div className="w-2 h-2 bg-[var(--text-secondary)] rounded-full typing-dot"></div>
                  <div className="w-2 h-2 bg-[var(--text-secondary)] rounded-full typing-dot"></div>
                </div>
             </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </main>

      {/* Input Area */}
      <footer className="p-4 glass-panel border-t border-[var(--border-color)]">
        <div className="max-w-4xl mx-auto w-full">
          <form onSubmit={handleSubmit} className="relative flex items-center gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Posez votre question..."
              className="w-full bg-[var(--bg-secondary)] text-[var(--text-primary)] border border-[var(--border-color)] rounded-xl py-3 pl-4 pr-12 focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)] focus:border-transparent transition-all placeholder-[var(--text-secondary)]"
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              className="absolute right-2 p-2 bg-[var(--accent-primary)] hover:bg-[var(--accent-secondary)] text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? <Loader2 size={20} className="animate-spin" /> : <Send size={20} />}
            </button>
          </form>
          <p className="text-center text-[10px] text-[var(--text-secondary)] mt-2">
            RAG Assistant peut faire des erreurs. Vérifiez les sources.
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;
