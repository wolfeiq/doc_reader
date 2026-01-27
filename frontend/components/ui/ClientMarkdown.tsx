'use client';

import React, { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/cjs/styles/prism';
import { Terminal } from 'lucide-react';

interface ClientMarkdownProps {
  content: string;
}

const ClientMarkdown: React.FC<ClientMarkdownProps> = ({ content }) => {
  const processedContent = useMemo(() => {
    if (!content) return '';
    return content
      .replace(/(\[[^\]]+\])\[[^\]]*\]/g, '$1') 
      .replace(/^[!?]{3}\s+\w+\s*/gm, '')      
      .replace(/\n([^\n])/g, '\n\n$1');        
  }, [content]);

  return (
    <div className="bg-[#0f172a] text-slate-300 p-6 md:p-8 rounded-xl selection:bg-indigo-500/30 overflow-hidden">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ ...props }) => <h1 className="text-3xl font-extrabold text-white mb-4 border-b border-slate-800 pb-2 tracking-tight" {...props} />,
          h2: ({ ...props }) => <h2 className="text-xl font-bold text-slate-100 mt-6 mb-3 border-l-4 border-indigo-500 pl-3" {...props} />,
          
          p: ({ ...props }) => (
            <p className="my-2 leading-tight text-slate-400 [overflow-wrap:anywhere] break-words" {...props} />
          ),

          ul: ({ ...props }) => <ul className="list-none space-y-1 my-2" {...props} />,
          li: ({ children, ...props }) => (
            <li className="relative pl-5 text-slate-400 leading-tight text-sm" {...props}>
              <span className="absolute left-0 top-[0.5em] w-1.5 h-1.5 rounded-full bg-indigo-500 shrink-0" />
              <span className="block">{children}</span>
            </li>
          ),

          code({ inline, className, children, ...props }: { inline?: boolean; className?: string; children?: React.ReactNode }) {
            const match = /language-(\w+)/.exec(className || '');
            const language = match ? match[1] : '';

            if (!inline && language) {
              return (
                <div className="my-4 rounded-lg border border-slate-800 bg-[#1e1e1e] shadow-xl overflow-hidden w-full">
                  <div className="flex items-center gap-2 px-3 py-1 border-b border-slate-800/50 bg-[#252526]">
                    <Terminal className="h-3 w-3 text-slate-500" />
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">{language}</span>
                  </div>
                  <SyntaxHighlighter
                    style={vscDarkPlus}
                    language={language}
                    PreTag="div"
                    customStyle={{ 
                        margin: 0, 
                        padding: '0.75rem 1rem', 
                        fontSize: '0.75rem', 
                        lineHeight: '1.3', 
                        background: 'transparent' 
                    }}
                    {...props}
                  >
                    {String(children).replace(/\n$/, '')}
                  </SyntaxHighlighter>
                </div>
              );
            }
            
            return (
              <code
                className="bg-slate-800/80 text-indigo-300 px-1.5 py-0 rounded text-[0.85em] font-mono border border-indigo-500/20 [overflow-wrap:anywhere] break-all inline-block align-middle"
                {...props}
              >
                {children}
              </code>
            );
          },
        }}
      >
        {processedContent}
      </ReactMarkdown>
    </div>
  );
};

export default ClientMarkdown;