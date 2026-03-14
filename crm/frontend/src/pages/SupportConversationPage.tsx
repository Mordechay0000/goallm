/**
 * Support ticket – content directly on page (no frame).
 * Structure: wrapper > chat-discussion > chat-message left + compose (message with buttons, textarea, Send, Close).
 * Tickets can have an attached request (בקשה לפתיחה); shown as block + status. User can send "edited copy" as reply; admin can edit/approve/reject.
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
  Chip,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Checkbox,
  FormControlLabel,
} from '@mui/material';
import { Notifications as NotificationsIcon, ArrowBack as ArrowBackIcon, Send as SendIcon, Edit as EditIcon, Check as CheckIcon, Close as CloseIcon } from '@mui/icons-material';
import ReactMarkdown from 'react-markdown';
import { supportApi } from '../api/support';
import type { SupportTicket, SupportReply, SupportAttachmentItem, AttachedRequestSnapshot } from '../api/support';
import SupportAttachBar from '../components/SupportAttachBar';
import { getAvatarUrl } from '../api/auth';
import { useAuthStore } from '../store/authStore';
import { ruleRequestsApi } from '../api/ruleRequests';
import type { RuleRequest, RuleConflictRule } from '../api/ruleRequests';
import { TagInput } from '../components/TagInput';
import RuleConflictDialog from '../components/RuleConflictDialog';

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

const REQUEST_STATUS_LABELS: Record<string, string> = {
  pending: 'ממתין לאישור',
  approved: 'אושר',
  rejected: 'נדחה',
};

/** Renders attached request snapshot (client view – as user sent it) + status badge */
const AttachedRequestBlock: React.FC<{
  snapshotJson: string | null | undefined;
  status?: string | null;
  compact?: boolean;
}> = ({ snapshotJson, status, compact }) => {
  if (!snapshotJson) return null;
  let snapshot: AttachedRequestSnapshot;
  try {
    snapshot = JSON.parse(snapshotJson) as AttachedRequestSnapshot;
  } catch {
    return null;
  }
  const isFile = snapshot.request_type === 'file';
  return (
    <Box sx={{ mt: 1, p: 1.5, bgcolor: 'action.hover', borderRadius: 1, border: '1px solid', borderColor: 'divider' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 0.5, mb: 0.5 }}>
        <Typography variant="caption" fontWeight={600}>
          {isFile ? 'בקשה לפתיחת קובץ' : snapshot.request_type === 'open' ? 'בקשה לפתיחת אתר' : 'בקשה לשינוי'}
        </Typography>
        {status && (
          <Chip
            size="small"
            label={REQUEST_STATUS_LABELS[status] || status}
            color={status === 'approved' ? 'success' : status === 'rejected' ? 'error' : 'default'}
            sx={{ height: 20 }}
          />
        )}
      </Box>
      {!compact && (
        <>
          {isFile ? (
            <>
              <Typography variant="body2" component="div">קישור: {snapshot.url || '—'}</Typography>
              {snapshot.notes && <Typography variant="body2" component="div" sx={{ mt: 0.5 }}>תיאור: {snapshot.notes}</Typography>}
            </>
          ) : (
            <>
              <Typography variant="body2" component="div">כתובת: {snapshot.url || snapshot.domain_pattern || '—'}</Typography>
              {snapshot.action && <Typography variant="body2" component="span">פעולה: {snapshot.action === 'allow' ? 'אפשר' : 'חסום'} </Typography>}
              {snapshot.tags && snapshot.tags.length > 0 && <Typography variant="body2" component="span">תגיות: {snapshot.tags.join(', ')}</Typography>}
            </>
          )}
        </>
      )}
    </Box>
  );
};

const MessageBlock: React.FC<{
  name: string;
  avatarUrl?: string | null;
  date: string;
  content: string;
  attachments?: SupportAttachmentItem[];
  attachedRequestSnapshot?: string | null;
  /** When isOpening: attached request (בקשה) shown inside this message frame */
  openingRequestSnapshot?: string | null;
  openingRequestStatus?: string | null;
  /** When isOpening: action buttons (ערוך, אישור, דחה) rendered inside the message below the request */
  openingRequestActions?: React.ReactNode;
  isUnread?: boolean;
  variant?: 'user' | 'system';
  isOpening?: boolean;
}> = ({ name, avatarUrl, date, content, attachments, attachedRequestSnapshot, openingRequestSnapshot, openingRequestStatus, openingRequestActions, isUnread, variant = 'user', isOpening = false }) => {
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
                bgcolor: 'rgba(91, 33, 182, 0.06)',
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
        {attachedRequestSnapshot && (
          <Box sx={{ mt: 1 }}>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.25 }}>עותק ערוך של הבקשה</Typography>
            <AttachedRequestBlock snapshotJson={attachedRequestSnapshot} compact />
          </Box>
        )}
        {isOpening && openingRequestSnapshot && (
          <Box sx={{ mt: 1.5 }}>
            <AttachedRequestBlock snapshotJson={openingRequestSnapshot} status={openingRequestStatus ?? undefined} />
            {openingRequestActions && (
              <Box sx={{ mt: 1 }}>{openingRequestActions}</Box>
            )}
          </Box>
        )}
        <MessageAttachments items={attachments || []} resolveUrl={getAvatarUrl} />
      </Box>
    </Box>
  );
};

const SupportConversationPage: React.FC<{ isAdmin?: boolean }> = ({ isAdmin }) => {
  const { ticketId } = useParams<{ ticketId: string }>();
  const navigate = useNavigate();
  const { user: currentUser } = useAuthStore();
  const [ticket, setTicket] = useState<SupportTicket | null>(null);
  const [replies, setReplies] = useState<SupportReply[]>([]);
  const [replyContent, setReplyContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [replySubmitting, setReplySubmitting] = useState(false);
  const [closing, setClosing] = useState(false);
  const [error, setError] = useState('');
  const [showEditCopyForm, setShowEditCopyForm] = useState(false);
  const [editCopySnapshot, setEditCopySnapshot] = useState<AttachedRequestSnapshot | null>(null);
  const [adminActionLoading, setAdminActionLoading] = useState(false);
  const [approveSuccessMessage, setApproveSuccessMessage] = useState<string | null>(null);
  const [approveConflictData, setApproveConflictData] = useState<{
    request: RuleRequest;
    existing_rule: RuleConflictRule;
    proposed_rule: RuleConflictRule;
  } | null>(null);

  const listPath = isAdmin ? '/admin/support' : '/support';
  const attachedRequestPending = ticket?.attached_request_status === 'pending';

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
      // עדכון מיידי של המספר בתפריט (פניות שלא נקראו) – listReplies סימן את השיחה כנקראה
      window.dispatchEvent(new CustomEvent('support-stats-refresh'));
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

  useEffect(() => {
    if (!currentUser || !ticket) return;
    if (isAdmin && !currentUser.is_admin) {
      navigate('/support');
      return;
    }
    if (!isAdmin && ticket.user_id !== currentUser.id) {
      navigate('/support');
      return;
    }
    // Do not redirect admins from /support/:id to /admin/support/:id – the route determines context:
    // from "הפניות שלי" → /support/:id (user view); from "פניות שהתקבלו" → /admin/support/:id (admin view).
  }, [currentUser, ticket, isAdmin, ticketId, navigate]);

  const handleBack = () => navigate(listPath);

  const handleAddReply = async (opts?: { attached_request_snapshot?: string }) => {
    if (!ticket) return;
    const content = (opts?.attached_request_snapshot ? '' : replyContent.trim());
    const snapshot = opts?.attached_request_snapshot;
    if (!content && !snapshot) return;
    setReplySubmitting(true);
    setError('');
    try {
      await supportApi.addReply(ticket.id, {
        content,
        ...(snapshot && { attached_request_snapshot: snapshot }),
        // לפי מקום השליחה: פניות שלי → תגובת משתמש; פניות שהתקבלו (אדמין) → תגובת תמיכה
        is_support_reply: isAdmin === true,
      });
      setReplyContent('');
      setShowEditCopyForm(false);
      setEditCopySnapshot(null);
      await load();
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string } } };
      setError(ax?.response?.data?.detail || 'שגיאה בשליחת תגובה');
    } finally {
      setReplySubmitting(false);
    }
  };

  const handleStartEditCopy = () => {
    if (!ticket?.request_snapshot_for_client) return;
    try {
      const snap = JSON.parse(ticket.request_snapshot_for_client) as AttachedRequestSnapshot;
      setEditCopySnapshot({ ...snap });
      setShowEditCopyForm(true);
    } catch {
      setError('לא ניתן לפרסר את הבקשה');
    }
  };

  const handleSendEditedCopy = async () => {
    if (!editCopySnapshot || !ticket) return;
    if (editCopySnapshot.request_type === 'file' && !(editCopySnapshot.notes || '').trim()) {
      setError('נא לתאר את הקובץ');
      return;
    }
    if ((editCopySnapshot.request_type === 'open' || editCopySnapshot.request_type === 'change') && !(editCopySnapshot.url || '').trim()) {
      setError('נא להזין כתובת');
      return;
    }
    await handleAddReply({ attached_request_snapshot: JSON.stringify(editCopySnapshot) });
  };

  const handleApproveRequest = async (opts?: { force_update?: boolean; skip_rule_update?: boolean }) => {
    if (!ticket?.attached_rule_request_id) return;
    const requestId = approveConflictData?.request?.id ?? ticket.attached_rule_request_id;
    setAdminActionLoading(true);
    setError('');
    setApproveSuccessMessage(null);
    try {
      const res = await ruleRequestsApi.approve(requestId, {
        force_update: opts?.force_update,
        skip_rule_update: opts?.skip_rule_update,
      });
      if (res.status === 'conflict') {
        setApproveConflictData({ request: res.request, existing_rule: res.existing_rule, proposed_rule: res.proposed_rule });
        setAdminActionLoading(false);
        return;
      }
      setApproveConflictData(null);
      const isFile = res?.request?.request_type === 'file';
      if (res.already_existed_identical) {
        setApproveSuccessMessage('הכלל כבר קיים ולכן לא נוסף. הבקשה סומנה כאושרה.');
      } else {
        setApproveSuccessMessage(isFile ? 'הבקשה אושרה והקובץ נוסף לרשימת הקבצים המותרים' : 'הבקשה אושרה והכלל נוסף לרשימה הגלובלית');
      }
      await load();
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string | unknown } }; message?: string };
      const d = ax?.response?.data?.detail;
      setError((typeof d === 'string' ? d : null) || ax?.message || 'שגיאה באישור');
    } finally {
      setAdminActionLoading(false);
    }
  };

  const handleConflictUpdate = () => handleApproveRequest({ force_update: true });
  const handleConflictLeave = () => handleApproveRequest({ skip_rule_update: true });

  const handleRejectRequest = async () => {
    if (!ticket?.attached_rule_request_id) return;
    if (!replyContent.trim()) {
      setError('בדחיית הבקשה נא להוסיף תגובה ללקוח (סיבת הדחייה).');
      return;
    }
    setAdminActionLoading(true);
    setError('');
    try {
      await ruleRequestsApi.reject(ticket.attached_rule_request_id);
      await supportApi.addReply(ticket.id, { content: replyContent.trim() });
      setReplyContent('');
      await load();
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string } } };
      setError(ax?.response?.data?.detail || 'שגיאה בדחייה');
    } finally {
      setAdminActionLoading(false);
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
      <Container maxWidth="lg" sx={{ mt: { xs: 2, sm: 4 }, mb: 4, px: { xs: 2 } }}>
        <Button startIcon={<ArrowBackIcon />} onClick={handleBack} color="secondary" variant="outlined" sx={{ mb: 2 }}>
          חזרה לרשימת הפניות
        </Button>
        <Box sx={{ py: 4, textAlign: 'center', color: 'text.secondary' }}>
          {loading ? 'טוען...' : 'פנייה לא נמצאה'}
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ mt: { xs: 2, sm: 4 }, mb: 4, px: { xs: 2 } }} className="page-section container-content">
      <Box className="page-title-section" sx={{ mb: 3 }}>
        <Button startIcon={<ArrowBackIcon />} onClick={handleBack} color="secondary" variant="outlined" sx={{ mb: 1 }}>
          חזרה לרשימת הפניות
        </Button>
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
        {approveSuccessMessage && (
          <Box sx={{ py: 1, mb: 2, bgcolor: 'success.light', color: 'success.contrastText', px: 2, borderRadius: 1, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span>{approveSuccessMessage}</span>
            <Button size="small" onClick={() => setApproveSuccessMessage(null)}>סגור</Button>
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
          openingRequestSnapshot={ticket.request_snapshot_for_client}
          openingRequestStatus={ticket.attached_request_status}
          openingRequestActions={
            ticket.request_snapshot_for_client ? (
              <>
                {!isAdmin && attachedRequestPending && (
                  <Button size="small" startIcon={<EditIcon />} onClick={handleStartEditCopy}>
                    ערוך עותק
                  </Button>
                )}
                {isAdmin && ticket.attached_rule_request_id && (
                  <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
                    <Button size="small" startIcon={<EditIcon />} onClick={() => navigate(`/admin/requests?request_id=${ticket.attached_rule_request_id}`)}>
                      ערוך בקשה (רק למנהל)
                    </Button>
                    {attachedRequestPending && (
                      <>
                        <Button size="small" color="success" startIcon={<CheckIcon />} onClick={() => handleApproveRequest()} disabled={adminActionLoading}>
                          {adminActionLoading ? 'מאשר...' : 'אישור'}
                        </Button>
                        <Button size="small" color="error" startIcon={<CloseIcon />} onClick={handleRejectRequest} disabled={adminActionLoading}>
                          דחה (יש להוסיף תגובה למטה)
                        </Button>
                      </>
                    )}
                  </Box>
                )}
              </>
            ) : undefined
          }
        />
        {showEditCopyForm && editCopySnapshot && (
          <Box sx={{ mb: 2, ml: { xs: 0, sm: 6 }, p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 1, bgcolor: 'background.paper' }}>
            <Typography variant="subtitle2" sx={{ mb: 1 }}>עותק ערוך של הבקשה – שמירה תשלח כתגובה חדשה</Typography>
            {editCopySnapshot.request_type === 'file' ? (
              <>
                <TextField fullWidth label="קישור לקובץ" value={editCopySnapshot.url || ''} onChange={(e) => setEditCopySnapshot((s) => s ? { ...s, url: e.target.value } : null)} size="small" sx={{ mb: 1 }} />
                <TextField fullWidth label="תיאור הקובץ" value={editCopySnapshot.notes || ''} onChange={(e) => setEditCopySnapshot((s) => s ? { ...s, notes: e.target.value } : null)} multiline minRows={2} size="small" sx={{ mb: 1 }} />
              </>
            ) : (
              <>
                <TextField fullWidth label="כתובת" value={editCopySnapshot.url || ''} onChange={(e) => setEditCopySnapshot((s) => s ? { ...s, url: e.target.value } : null)} size="small" sx={{ mb: 1 }} />
                <FormControl fullWidth size="small" sx={{ mb: 1 }}>
                  <InputLabel>פעולה</InputLabel>
                  <Select value={editCopySnapshot.action || 'allow'} label="פעולה" onChange={(e) => setEditCopySnapshot((s) => s ? { ...s, action: e.target.value as 'allow' | 'block' } : null)}>
                    <MenuItem value="allow">אפשר</MenuItem>
                    <MenuItem value="block">חסום</MenuItem>
                  </Select>
                </FormControl>
                <FormControlLabel control={<Checkbox checked={editCopySnapshot.include_subdomains || false} onChange={(e) => setEditCopySnapshot((s) => s ? { ...s, include_subdomains: e.target.checked } : null)} />} label="כולל סאב-דומיינים" sx={{ display: 'block', mb: 1 }} />
                <TagInput value={editCopySnapshot.tags || []} onChange={(tags) => setEditCopySnapshot((s) => s ? { ...s, tags } : null)} label="תגיות" helperText="" />
              </>
            )}
            <Box sx={{ mt: 1, display: 'flex', gap: 1 }}>
              <Button size="small" variant="contained" onClick={handleSendEditedCopy} disabled={replySubmitting}>
                {replySubmitting ? 'שולח...' : 'שמור ושלח'}
              </Button>
              <Button size="small" variant="outlined" onClick={() => { setShowEditCopyForm(false); setEditCopySnapshot(null); }}>ביטול</Button>
            </Box>
          </Box>
        )}
        {replies.map((r) => (
          <MessageBlock
            key={r.id}
            variant={r.is_support_reply ? 'system' : 'user'}
            isOpening={false}
            name={[r.author_first_name, r.author_last_name].filter(Boolean).join(' ') || (r.is_support_reply ? 'תמיכה' : 'משתמש')}
            avatarUrl={r.author_avatar_url}
            date={formatRelative(r.created_at)}
            content={r.content}
            attachments={r.attachments}
            attachedRequestSnapshot={r.attached_request_snapshot}
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
              buttonsTabIndex={-1}
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
              placeholder="כתוב הודעה, או בחר קובץ / הדבק מהלוח (⌘+Enter לשליחה)"
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
                onClick={() => handleAddReply()}
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

      <RuleConflictDialog
        open={!!approveConflictData}
        onClose={() => !adminActionLoading && setApproveConflictData(null)}
        data={approveConflictData}
        approving={adminActionLoading}
        onUpdate={handleConflictUpdate}
        onLeave={handleConflictLeave}
      />
    </Container>
  );
};

export default SupportConversationPage;
