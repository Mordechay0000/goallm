/**
 * Renders markdown content (no formatting toolbar - plain markdown source).
 */
import React from 'react';
import ReactMarkdown from 'react-markdown';
import { Typography } from '@mui/material';

const MarkdownContent: React.FC<{ content: string }> = ({ content }) => {
  return (
    <ReactMarkdown
      components={{
        p: ({ children }) => <Typography component="p" variant="body1" sx={{ mb: 1 }}>{children}</Typography>,
        strong: ({ children }) => <strong>{children}</strong>,
        em: ({ children }) => <em>{children}</em>,
        ul: ({ children }) => <Typography component="ul" sx={{ pl: 2, mb: 1 }}>{children}</Typography>,
        ol: ({ children }) => <Typography component="ol" sx={{ pl: 2, mb: 1 }}>{children}</Typography>,
        li: ({ children }) => <Typography component="li" variant="body1">{children}</Typography>,
        code: ({ children }) => (
          <Typography
            component="code"
            sx={{
              bgcolor: 'action.hover',
              px: 0.5,
              borderRadius: 0.5,
              fontFamily: 'monospace',
              fontSize: '0.9em',
            }}
          >
            {children}
          </Typography>
        ),
        pre: ({ children }) => (
          <Typography
            component="pre"
            sx={{
              bgcolor: 'action.hover',
              p: 1.5,
              borderRadius: 1,
              overflow: 'auto',
              fontFamily: 'monospace',
              fontSize: '0.85rem',
              whiteSpace: 'pre-wrap',
              mb: 1,
            }}
          >
            {children}
          </Typography>
        ),
        h1: ({ children }) => <Typography variant="h6" sx={{ mt: 1.5, mb: 0.5 }}>{children}</Typography>,
        h2: ({ children }) => <Typography variant="subtitle1" sx={{ mt: 1.5, mb: 0.5, fontWeight: 600 }}>{children}</Typography>,
        h3: ({ children }) => <Typography variant="subtitle2" sx={{ mt: 1, mb: 0.5 }}>{children}</Typography>,
        a: ({ href, children }) => (
          <a href={href} target="_blank" rel="noopener noreferrer" style={{ color: 'inherit', textDecoration: 'underline' }}>
            {children}
          </a>
        ),
      }}
    >
      {content || ''}
    </ReactMarkdown>
  );
};

export default MarkdownContent;
