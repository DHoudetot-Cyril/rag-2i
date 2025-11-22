import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { Send, Bot, User, FileText, Menu, X, Plus, Trash2 } from 'lucide-react';

function App() {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Bonjour ! Je suis votre assistant RAG. Comment puis-je vous aider aujourd\'hui ?', files: [] }
  ]);
  const [documents, setDocuments] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false); // Mobile sidebar toggle
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Fetch documents on load
  useEffect(() => {
    const fetchDocuments = async () => {
      try {
        const response = await axios.get('http://localhost:8000/documents');
        setDocuments(response.data);
      } catch (error) {
        console.error("Error fetching documents:", error);
      }
    };
    fetchDocuments();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage = { role: 'user', content: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await axios.post('http://localhost:8000/query', {
        question: userMessage.content,
        min_score: 0.01
      });

      const data = response.data;

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
    <div className="flex h-screen bg-[var(--bg-primary)] text-[var(--text-primary)] font-sans overflow-hidden">

      {/* Mobile Sidebar Overlay */}
      {isSidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-20 md:hidden"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed md:static inset-y-0 left-0 z-30 w-[260px] bg-[var(--bg-sidebar)] flex flex-col transition-transform duration-300 ease-in-out
        ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
      `}>
        <div className="p-2 flex-1 overflow-y-auto">
          <button
            onClick={() => setMessages([{ role: 'assistant', content: 'Bonjour ! Je suis votre assistant RAG. Comment puis-je vous aider aujourd\'hui ?', files: [] }])}
            className="w-full flex items-center gap-3 px-3 py-3 rounded-md border border-white/20 hover:bg-[var(--bg-secondary)] transition-colors text-sm text-white mb-4"
          >
            <Plus size={16} />
            Nouveau chat
          </button>

          <div className="mb-2 px-3 text-xs font-medium text-[var(--text-secondary)] uppercase">
            Documents ingérés
          </div>

          <div className="space-y-1">
            {documents.length === 0 ? (
              <div className="px-3 py-2 text-sm text-[var(--text-secondary)] italic">Aucun document</div>
            ) : (
              documents.map((doc, idx) => (
                <div key={idx} className="flex items-center gap-3 px-3 py-3 text-sm text-[var(--text-primary)] hover:bg-[#2A2B32] rounded-md cursor-pointer transition-colors group">
                  <FileText size={16} className="text-[var(--text-secondary)] group-hover:text-white" />
                  <div className="flex-1 truncate">
                    <div className="truncate">{doc.filename}</div>
                    <div className="text-[10px] text-[var(--text-secondary)]">{new Date(doc.ingested_at).toLocaleDateString()}</div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="p-3 border-t border-white/20">
          <div className="flex items-center gap-3 px-3 py-3 text-sm hover:bg-[#2A2B32] rounded-md cursor-pointer transition-colors">
            <User size={16} />
            <span>Utilisateur</span>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col relative h-full">
        {/* Mobile Header */}
        <div className="md:hidden flex items-center p-2 border-b border-white/10 bg-[var(--bg-primary)] text-white sticky top-0 z-10">
          <button onClick={() => setIsSidebarOpen(true)} className="p-2 hover:bg-[var(--bg-secondary)] rounded-md">
            <Menu size={24} />
          </button>
          <span className="ml-2 font-medium">RAG Assistant</span>
        </div>

        {/* Chat Area */}
        <div className="flex-1 overflow-y-auto w-full">
          <div className="flex flex-col pb-32">
            {messages.map((msg, index) => (
              <div
                key={index}
                className={`chat-message ${msg.role} w-full border-b border-black/10 dark:border-gray-900/50 text-gray-800 dark:text-gray-100`}
              >
                <div className="max-w-3xl mx-auto gap-4 md:gap-6 flex p-4 md:py-6">
                  <div className="flex-shrink-0 flex flex-col relative items-end">
                    <div className={`w-[30px] h-[30px] rounded-sm flex items-center justify-center ${msg.role === 'assistant' ? 'bg-[#10a37f]' : 'bg-[#5436DA]'}`}>
                      {msg.role === 'assistant' ? <Bot size={20} className="text-white" /> : <User size={20} className="text-white" />}
                    </div>
                  </div>

                  <div className="relative flex-1 overflow-hidden">
                    <div className="prose prose-invert max-w-none whitespace-pre-wrap">
                      {msg.content}
                    </div>

                    {/* Sources */}
                    {msg.files && msg.files.length > 0 && (
                      <div className="mt-4 pt-2">
                        <div className="text-xs font-bold text-[var(--text-secondary)] uppercase mb-2">Sources :</div>
                        <div className="flex flex-wrap gap-2">
                          {msg.files.map((file, fIndex) => (
                            <div
                              key={fIndex}
                              className="text-xs bg-black/20 hover:bg-black/40 transition-colors px-2 py-1 rounded flex items-center gap-1 cursor-help"
                              title={`Score: ${file.score}`}
                            >
                              <FileText size={12} />
                              <span className="truncate max-w-[200px]">{file.file_path.split('/').pop() || file.file_path}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="chat-message assistant w-full">
                <div className="max-w-3xl mx-auto gap-4 md:gap-6 flex p-4 md:py-6">
                  <div className="flex-shrink-0 flex flex-col relative items-end">
                    <div className="w-[30px] h-[30px] rounded-sm bg-[#10a37f] flex items-center justify-center">
                      <Bot size={20} className="text-white" />
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="w-2 h-2 bg-gray-400 rounded-full typing-dot"></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full typing-dot"></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full typing-dot"></div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input Area */}
        <div className="absolute bottom-0 left-0 w-full bg-gradient-to-t from-[var(--bg-primary)] via-[var(--bg-primary)] to-transparent pt-10 pb-6 px-4">
          <div className="max-w-3xl mx-auto">
            <form onSubmit={handleSubmit} className="relative flex items-center w-full p-3 bg-[var(--input-bg)] rounded-xl shadow-xs border border-black/10 dark:border-gray-900/50 focus-within:border-gray-500/50 ring-offset-2 focus-within:ring-offset-2 ring-blue-600/50">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Envoyer un message..."
                className="w-full bg-transparent border-none focus:ring-0 focus:outline-none text-white placeholder-gray-400 pl-2 pr-10 m-0 resize-none"
                disabled={isLoading}
              />
              <button
                type="submit"
                disabled={isLoading || !input.trim()}
                className="absolute right-3 p-1 rounded-md text-gray-400 hover:bg-black/50 hover:text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <Send size={16} />
              </button>
            </form>
            <div className="text-center text-xs text-gray-400 mt-2">
              RAG Assistant peut faire des erreurs. Envisagez de vérifier les informations importantes.
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
