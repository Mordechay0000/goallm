/**
 * Support ticket – content directly on page (no frame).
 * Structure: wrapper > chat-discussion > chat-message left + compose (message with buttons, textarea, Send, Close).
 */
import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Container,
  Paper,
  Typography,
  Button,
  TextField,
  Avatar,
  Link,
} from '@mui/material';
import { Notifications as NotificationsIcon, ArrowBack as ArrowBackIcon, Send as SendIcon } from '@mui/icons-material';
import ReactMarkdown from 'react-markdown';
import { supportApi } from '../api/support';
import type { SupportTicket, SupportReply, SupportAttachmentItem } from '../api/support';
import SupportAttachBar from '../components/SupportAttachBar';
import { getAvatarUrl } from '../api/auth';

/** Renders markdown; links to audio/video are shown as players, other links as normal. */
const SupportMessageContent: React.FC<{ content: string; resolveUrl: (url: string) => string }> = ({ content, resolveUrl }) => {
  const linkText = (children: React.ReactNode): string => {
    if (typeof children === 'string') return children;
    return React.Children.toArray(children).map((c) => {
      if (typeof c === 'string') return c;
      const el = c as React.ReactElement<{ children?: React.ReactNode }>;
      return el?.props?.children != null ? String(el.props.children) : '';
    }).join('').trim();
  };
  const isMediaLink = (href: string, label: string): 'audio' | 'video' | null => {
    const h = (href || '').toLowerCase();
    const n = (label || '').toLowerCase();
    if (/voice-.*\.webm$/i.test(n) || /\.(mp3|wav|ogg|m4a)(\?|$)/.test(n) || /\.(mp3|wav|ogg|m4a)(\?|$)/.test(h)) return 'audio';
    if (/screen-.*\.webm$/i.test(n) || /\.(mp4|webm|mov)(\?|$)/.test(n) || /\.(mp4|webm|mov)(\?|$)/.test(h)) return 'video';
    return null;
  };
  return (
    <ReactMarkdown
      components={{
        p: ({ children }) => <Typography component="p" variant="body1" sx={{ mb: 1 }}>{children}</Typography>,
        strong: ({ children }) => <strong>{children}</strong>,
        em: ({ children }) => <em>{children}</em>,
        ul: ({ children }) => <Typography component="ul" sx={{ pl: 2, mb: 1 }}>{children}</Typography>,
        ol: ({ children }) => <Typography component="ol" sx={{ pl: 2, mb: 1 }}>{children}</Typography>,
        li: ({ children }) => <Typography component="li" variant="body1">{children}</Typography>,
        code: ({ children }) => <Typography component="code" sx={{ bgcolor: 'action.hover', px: 0.5, borderRadius: 0.5, fontFamily: 'monospace', fontSize: '0.9em' }}>{children}</Typography>,
        pre: ({ children }) => <Typography component="pre" sx={{ bgcolor: 'action.hover', p: 1.5, borderRadius: 1, overflow: 'auto', fontFamily: 'monospace', fontSize: '0.85rem', whiteSpace: 'pre-wrap', mb: 1 }}>{children}</Typography>,
        h1: ({ children }) => <Typography variant="h6" sx={{ mt: 1.5, mb: 0.5 }}>{children}</Typography>,
        h2: ({ children }) => <Typography variant="subtitle1" sx={{ mt: 1.5, mb: 0.5, fontWeight: 600 }}>{children}</Typography>,
        h3: ({ children }) => <Typography variant="subtitle2" sx={{ mt: 1, mb: 0.5 }}>{children}</Typography>,
        a: ({ href, children }) => {
          const label = linkText(children);
          const resolved = resolveUrl(href || '');
          const media = href ? isMediaLink(href, label) : null;
          if (media === 'audio') {
            return (
              <Box sx={{ mt: 0.5, mb: 0.5 }}>
                <Typography component="span" variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.25 }}>{label}</Typography>
                <audio controls src={resolved} style={{ maxWidth: '100%', height: 36 }} />
              </Box>
            );
          }
          if (media === 'video') {
            return (
              <Box sx={{ mt: 0.5, mb: 0.5 }}>
                <Typography component="span" variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.25 }}>{label}</Typography>
                <video controls src={resolved} style={{ maxWidth: '100%', maxHeight: 320, borderRadius: 4 }} />
              </Box>
            );
          }
          return (
            <a href={resolved} target="_blank" rel="noopener noreferrer" style={{ color: 'inherit', textDecoration: 'underline' }}>
              {children}
            </a>
          );
        },
      }}
    >
      {content || ''}
    </ReactMarkdown>
  );
};

function formatRelative(ts: number): string {
  const now = Date.now() / 1000;
  const diff = now - ts;
  if (diff < 60) return 'עכשיו';
  if (diff < 3600) return `לפני ${Math.floor(diff / 60)} דקות`;
  if (diff < 86400) return `לפני ${Math.floor(diff / 3600)} שעות`;
  if (diff < 86400 * 7) return `לפני ${Math.floor(diff / 86400)} ימים`;
  if (diff < 86400 * 30) return `לפני ${Math.floor(diff / (86400 * 7))} שבועות`;
  if (diff < 86400 * 365) return `לפני ${Math.floor(diff / (86400 * 30))} חודשים`;
  return `לפני ${Math.floor(diff / (86400 * 365))} שנים`;
}

type AttachmentKind = 'audio' | 'video' | 'image' | 'traffic' | 'file';

function getAttachmentKind(name: string, url: string): AttachmentKind {
  const u = (url || '').toLowerCase();
  const n = (name || '').toLowerCase();
  if (u.includes('traffic/view') || n.includes('תעבורה')) return 'traffic';
  if (/voice-.*\.webm$/i.test(n) || /\.(mp3|wav|ogg|m4a)(\?|$)/.test(n) || /\.(mp3|wav|ogg|m4a)(\?|$)/.test(u)) return 'audio';
  if (/screen-.*\.webm$/i.test(n) || /\.(mp4|webm|mov)(\?|$)/.test(n) || /\.(mp4|webm|mov)(\?|$)/.test(u)) return 'video';
  if (/\.(png|jpe?g|gif|webp)(\?|$)/.test(n) || /\.(png|jpe?g|gif|webp)(\?|$)/.test(u)) return 'image';
  return 'file';
}

const MessageAttachments: React.FC<{
  items: SupportAttachmentItem[];
  resolveUrl: (url: string) => string;
}> = ({ items, resolveUrl }) => {
  if (!items?.length) return null;
  return (
    <Box sx={{ mt: 1, display: 'flex', flexDirection: 'column', gap: 1 }}>
      {items.map((a, i) => {
        const kind = getAttachmentKind(a.name, a.url);
        const fullUrl = resolveUrl(a.url);
        if (kind === 'audio') {
          return (
            <Box key={`${a.url}-${i}`} sx={{ maxWidth: '100%' }}>
              <Typography component="span" variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.25 }}>
                {a.name}
              </Typography>
              <audio controls src={fullUrl} style={{ maxWidth: '100%', height: 36 }} />
            </Box>
          );
        }
        if (kind === 'video') {
          return (
            <Box key={`${a.url}-${i}`} sx={{ maxWidth: '100%' }}>
              <Typography component="span" variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.25 }}>
                {a.name}
              </Typography>
              <video controls src={fullUrl} style={{ maxWidth: '100%', maxHeight: 320, borderRadius: 1 }} />
            </Box>
          );
        }
        if (kind === 'image') {
          return (
            <Box key={`${a.url}-${i}`}>
              <a href={fullUrl} target="_blank" rel="noopener noreferrer">
                <img src={fullUrl} alt={a.name} style={{ maxWidth: '100%', maxHeight: 400, borderRadius: 4, display: 'block' }} />
              </a>
              <Typography component="span" variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.25 }}>
                {a.name}
              </Typography>
            </Box>
          );
        }
        if (kind === 'traffic') {
          return (
            <Link key={`${a.url}-${i}`} href={fullUrl} target="_blank" rel="noopener noreferrer" sx={{ fontSize: '0.875rem' }}>
              🔗 {a.name}
            </Link>
          );
        }
        return (
          <Link key={`${a.url}-${i}`} href={fullUrl} target="_blank" rel="noopener noreferrer" sx={{ fontSize: '0.875rem' }}>
            📎 {a.name}
          </Link>
        );
      })}
    </Box>
  );
};

/** צבע קבוע לתגובות התמיכה (מערכת) – teal, שונה מצבע המשתמש */
const SYSTEM_MSG_BORDER = '#0d9488';
const SYSTEM_MSG_BG = 'rgba(13, 148, 136, 0.08)';

const MessageBlock: React.FC<{
  name: string;
  avatarUrl?: string | null;
  date: string;
  content: string;
  attachments?: SupportAttachmentItem[];
  isUnread?: boolean;
  /** הודעות המשתמש (פנייה + תגובותיו) – צבע ראשי; תגובות המערכת – צבע קבוע אחר */
  variant?: 'user' | 'system';
  /** רק בהודעה הראשונה (הפנייה) – להצגת תווית "פנייה" */
  isOpening?: boolean;
}> = ({ name, avatarUrl, date, content, attachments, isUnread, variant = 'user', isOpening = false }) => {
  const text = (content || '').trim();
  const fromUser = variant === 'user';
  return (
    <Box className="chat-message left" sx={{ display: 'flex', gap: 1.5, alignItems: 'flex-start', mb: 2 }}>
      <Avatar
        src={avatarUrl ? getAvatarUrl(avatarUrl) : undefined}
        sx={{ width: 38, height: 38, flexShrink: 0, borderRadius: '50%' }}
      >
        {name?.charAt(0) || '?'}
      </Avatar>
      <Box
        className="message"
        sx={{
          flex: 1,
          minWidth: 0,
          borderRadius: 1,
          border: '1px solid',
          borderRightWidth: 4,
          ...(fromUser
            ? {
                borderColor: 'primary.main',
                bgcolor: 'rgba(166, 78, 255, 0.06)',
                p: 2,
              }
            : {
                borderColor: SYSTEM_MSG_BORDER,
                bgcolor: SYSTEM_MSG_BG,
                p: 2,
              }),
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 0.5 }}>
          {fromUser && isOpening && (
            <Typography component="span" variant="caption" sx={{ bgcolor: 'primary.main', color: 'primary.contrastText', px: 1, py: 0.25, borderRadius: 0.5, fontWeight: 600, mr: 0.5 }}>
              פנייה
            </Typography>
          )}
          {fromUser && !isOpening && (
            <Typography component="span" variant="caption" color="primary.main" sx={{ fontWeight: 600, mr: 0.5 }}>
              משתמש
            </Typography>
          )}
          {!fromUser && (
            <Typography component="span" variant="caption" sx={{ bgcolor: SYSTEM_MSG_BORDER, color: '#fff', px: 1, py: 0.25, borderRadius: 0.5, fontWeight: 600, mr: 0.5 }}>
              תגובת התמיכה
            </Typography>
          )}
          <Typography component="span" variant="body2" fontWeight={600}>
            {name}
          </Typography>
          <Typography component="span" variant="caption" color="text.secondary">
            {date}
          </Typography>
          {isUnread && (
            <NotificationsIcon sx={{ fontSize: 16, color: 'primary.main' }} titleAccess="תגובה שלא נקראה" />
          )}
        </Box>
        {text && (
          <Typography component="div" variant="body2" sx={{ mt: 0.5, lineHeight: 1.55 }}>
            <SupportMessageContent content={text} resolveUrl={getAvatarUrl} />
          </Typography>
        )}
        <MessageAttachments items={attachments || []} resolveUrl={getAvatarUrl} />
      </Box>
    </Box>
  );
};

const SupportConversationPage: React.FC<{ isAdmin?: boolean }> = ({ isAdmin }) => {
  const { ticketId } = useParams<{ ticketId: string }>();
  const navigate = useNavigate();
  const [ticket, setTicket] = useState<SupportTicket | null>(null);
  const [replies, setReplies] = useState<SupportReply[]>([]);
  const [replyContent, setReplyContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [replySubmitting, setReplySubmitting] = useState(false);
  const [closing, setClosing] = useState(false);
  const [error, setError] = useState('');

  const listPath = isAdmin ? '/admin/support' : '/support';

  const load = async () => {
    const id = ticketId ? parseInt(ticketId, 10) : NaN;
    if (!id) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const [t, r] = await Promise.all([
        supportApi.getTicket(id),
        supportApi.listReplies(id),
      ]);
      setTicket(t);
      setReplies(r);
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string } } };
      setError(ax?.response?.data?.detail || 'שגיאה בטעינה');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [ticketId]);

  const handleBack = () => navigate(listPath);

  const handleAddReply = async () => {
    if (!ticket) return;
    if (!replyContent.trim()) return;
    setReplySubmitting(true);
    setError('');
    try {
      await supportApi.addReply(ticket.id, { content: replyContent.trim() });
      setReplyContent('');
      await load();
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string } } };
      setError(ax?.response?.data?.detail || 'שגיאה בשליחת תגובה');
    } finally {
      setReplySubmitting(false);
    }
  };

  const handleCloseRequest = async () => {
    if (!ticket) return;
    if (!window.confirm('לסגור ולמחוק את הפנייה? לא ניתן לשחזר.')) return;
    setClosing(true);
    setError('');
    try {
      await supportApi.deleteTicket(ticket.id);
      navigate(listPath);
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string } } };
      setError(ax?.response?.data?.detail || 'שגיאה בסגירת הפנייה');
    } finally {
      setClosing(false);
    }
  };

  const openerName =
    ticket?.user_first_name || ticket?.user_last_name
      ? [ticket.user_first_name, ticket.user_last_name].filter(Boolean).join(' ')
      : ticket?.user_phone || 'משתמש';

  if (loading || !ticket) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
        <Link component="button" variant="body2" onClick={handleBack} sx={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 0.5, mb: 2 }}>
          <ArrowBackIcon fontSize="small" /> חזרה
        </Link>
        <Box sx={{ py: 4, textAlign: 'center', color: 'text.secondary' }}>
          {loading ? 'טוען...' : 'פנייה לא נמצאה'}
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }} className="wrapper-content">
      <Box sx={{ mb: 3 }}>
        <Link component="button" variant="body2" onClick={handleBack} sx={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 0.5, mb: 1 }}>
          <ArrowBackIcon fontSize="small" /> חזרה
        </Link>
        <Typography variant="h5" component="h1" sx={{ fontWeight: 600, mb: 1 }}>
          #{ticket.id} · {ticket.subject}
        </Typography>
      </Box>

      <Paper sx={{ p: 3 }}>
        {error && (
          <Box sx={{ py: 1, mb: 2, bgcolor: 'error.light', color: 'error.contrastText', px: 2, borderRadius: 1 }}>
            {error}
          </Box>
        )}

        <Box className="chat-view-frame" sx={{ width: '100%' }}>
          <Box className="chat-discussion" sx={{ width: '100%' }}>
        <MessageBlock
          variant="user"
          isOpening
          name={openerName}
          avatarUrl={ticket.user_avatar_url}
          date={formatRelative(ticket.created_at)}
          content={ticket.content}
          attachments={ticket.attachments}
        />
        {replies.map((r) => (
          <MessageBlock
            key={r.id}
            variant={r.author_id === ticket.user_id ? 'user' : 'system'}
            isOpening={false}
            name={[r.author_first_name, r.author_last_name].filter(Boolean).join(' ') || (r.author_id === ticket.user_id ? 'משתמש' : 'תמיכה')}
            avatarUrl={r.author_avatar_url}
            date={formatRelative(r.created_at)}
            content={r.content}
            attachments={r.attachments}
            isUnread={r.is_unread}
          />
        ))}

        {/* אזור כתיבת תגובה – מסגרת מקווקו כדי להבדיל מההודעות */}
        <Box className="chat-message left" sx={{ display: 'flex', gap: 1.5, alignItems: 'flex-start', mt: 3 }}>
          <Box sx={{ width: 38, flexShrink: 0 }} />
          <Box
            className="message compose-area"
            sx={{
              flex: 1,
              minWidth: 0,
              borderRadius: 1,
              border: '2px dashed',
              borderColor: 'divider',
              bgcolor: 'action.hover',
              p: 2,
            }}
          >
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
              כתוב תגובה
            </Typography>
            <SupportAttachBar
              onAppendContent={(markdown) => setReplyContent((prev) => (prev ? prev + markdown : markdown.trim()))}
              onUpload={supportApi.uploadFile}
              disabled={replySubmitting}
            />
            <TextField
              fullWidth
              multiline
              minRows={4}
              value={replyContent}
              onChange={(e) => setReplyContent(e.target.value)}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                  e.preventDefault();
                  if (replyContent.trim() && !replySubmitting) handleAddReply();
                }
              }}
              placeholder="כתוב הודעה (⌘+Enter או Ctrl+Enter לשליחה)"
              variant="outlined"
              size="small"
              sx={{
                mt: 1,
                mb: 1,
                '& .MuiOutlinedInput-root': {
                  bgcolor: 'transparent',
                  minHeight: 120,
                  borderColor: 'divider',
                },
              }}
            />
            <Box className="ibox-tools" sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
              <Button
                variant="contained"
                color="primary"
                size="small"
                startIcon={<SendIcon />}
                onClick={handleAddReply}
                disabled={!replyContent.trim() || replySubmitting}
              >
                {replySubmitting ? 'שולח...' : 'שלח'}
              </Button>
              <Button
                variant="outlined"
                color="error"
                size="small"
                onClick={handleCloseRequest}
                disabled={closing}
              >
                סגור פנייה
              </Button>
            </Box>
          </Box>
        </Box>
        </Box>
        </Box>
      </Paper>
    </Container>
  );
};

export default SupportConversationPage;
