/**
 * New support ticket (פנייה). Optional: attach a request (בקשה לפתיחה) from ?attach=open|change|file&url=... or file_url=&filename=.
 */
import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Box,
  Container,
  Paper,
  Typography,
  Button,
  TextField,
  Link,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Checkbox,
  FormControlLabel,
} from '@mui/material';
import { ArrowBack as ArrowBackIcon, Send as SendIcon, Add as AddIcon } from '@mui/icons-material';
import { supportApi } from '../api/support';
import type { AttachedRequestSnapshot } from '../api/support';
import SupportAttachBar from '../components/SupportAttachBar';
import { TagInput } from '../components/TagInput';
import { parseUrl } from '../utils/urlParser';
import { processUrlInput } from '../utils/validation';

type AttachType = 'open' | 'change' | 'file' | null;

const SupportNewTicketPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const attachFromQuery = (searchParams.get('attach') || '').toLowerCase() as AttachType;
  const urlFromQuery = searchParams.get('url') || '';
  const requestUrlFromQuery = searchParams.get('request_url') || '';
  const fileUrlFromQuery = searchParams.get('file_url') || '';
  const filenameFromQuery = searchParams.get('filename') || '';

  const [subject, setSubject] = useState('');
  const [content, setContent] = useState('');
  const [attach, setAttach] = useState<AttachType>(null);

  // Open/change form: url = domain (כתובת אתר), requestUrl = full URL (כתובת מלאה)
  const [url, setUrl] = useState('');
  const [requestUrl, setRequestUrl] = useState('');
  const [action, setAction] = useState<'allow' | 'block'>('allow');
  const [includeSubdomains, setIncludeSubdomains] = useState(false);
  const [tags, setTags] = useState<string[]>([]);

  // File form
  const [fileUrl, setFileUrl] = useState('');
  const [filename, setFilename] = useState('');
  const [fileDescription, setFileDescription] = useState('');

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (attachFromQuery === 'open' || attachFromQuery === 'change') {
      setAttach(attachFromQuery);
      try {
        const decodedUrl = decodeURIComponent(urlFromQuery || '').replace(/^https?:\/\//, '').trim();
        setUrl(decodedUrl);
        const decodedRequestUrl = decodeURIComponent(requestUrlFromQuery || '').trim();
        setRequestUrl(decodedRequestUrl);
      } catch {
        setUrl(urlFromQuery);
        setRequestUrl(requestUrlFromQuery);
      }
      setSubject(attachFromQuery === 'open' ? 'בקשה לפתיחת אתר' : 'בקשה לשינוי');
    } else if (attachFromQuery === 'file') {
      setAttach('file');
      try {
        setFileUrl(decodeURIComponent(fileUrlFromQuery || '').trim());
        setFilename(decodeURIComponent(filenameFromQuery || '').trim());
      } catch {
        setFileUrl(fileUrlFromQuery);
        setFilename(filenameFromQuery);
      }
      setSubject(filenameFromQuery ? `פתיחת קובץ – ${decodeURIComponent(filenameFromQuery)}` : 'פתיחת קובץ');
    }
  }, [attachFromQuery, urlFromQuery, requestUrlFromQuery, fileUrlFromQuery, filenameFromQuery]);

  /** Typing in "כתובת אתר": only clean protocol and *. (no split), so "/" can be typed. */
  const handleWebsiteUrlChange = (value: string) => {
    const { cleaned, setSubdomains } = processUrlInput(value);
    if (setSubdomains) setIncludeSubdomains(true);
    setUrl(cleaned);
  };

  /** Paste in "כתובת אתר": extract domain → כתובת אתר, full URL → כתובת מלאה. */
  const handleWebsiteUrlPaste = (e: React.ClipboardEvent) => {
    const pasted = (e.clipboardData.getData('text') || '').trim();
    if (!pasted) return;
    e.preventDefault();
    const { cleaned, setSubdomains } = processUrlInput(pasted);
    if (setSubdomains) setIncludeSubdomains(true);
    const hasProtocol = pasted.includes('://');
    const hasPath = cleaned.includes('/');
    if (hasPath || hasProtocol) {
      setRequestUrl(cleaned);
      setUrl(hasPath ? parseUrl(cleaned).domain : cleaned);
    } else {
      setUrl(cleaned);
    }
  };

  const handleSubmit = async () => {
    setError('');
    if (!subject.trim()) {
      setError('נא להזין נושא');
      return;
    }
    if (!attach && !content.trim()) {
      setError('נא להזין תוכן');
      return;
    }
    if ((attach === 'open' || attach === 'change') && !content.trim()) {
      setError('חובה למלאות הסבר בתוכן הפנייה');
      return;
    }
    if (attach === 'file' && !fileDescription.trim()) {
      setError('נא לתאר את הקובץ (מה הוא מכיל, סוג, איך פותחים, מאיפה הורדת)');
      return;
    }
    if ((attach === 'open' || attach === 'change') && !url.trim()) {
      setError('נא להזין כתובת');
      return;
    }
    setSubmitting(true);
    try {
      let attached_request: AttachedRequestSnapshot | undefined;
      if (attach === 'open' || attach === 'change') {
        const urlForRule = includeSubdomains && !url.trim().startsWith('*.') ? `*.${url.trim()}` : url.trim();
        attached_request = {
          request_type: attach,
          url: urlForRule,
          request_url: requestUrl.trim() || undefined,
          action,
          include_subdomains: includeSubdomains,
          tags: tags.length > 0 ? tags : undefined,
        };
      } else if (attach === 'file') {
        attached_request = {
          request_type: 'file',
          url: fileUrl.trim(),
          notes: fileDescription.trim(),
        };
      }
      const ticket = await supportApi.createTicket({
        subject: subject.trim(),
        content: content.trim(),
        ...(attached_request && { attached_request }),
      });
      navigate(`/support/${ticket.id}`);
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string } } };
      setError(ax?.response?.data?.detail || 'שגיאה ביצירת פנייה');
    } finally {
      setSubmitting(false);
    }
  };

  const canSubmit = subject.trim() && (attach !== null ? (attach === 'file' ? fileDescription.trim() && fileUrl.trim() : url.trim() && content.trim()) : content.trim());

  return (
    <Container maxWidth="lg" sx={{ mt: { xs: 2, sm: 4 }, mb: 4, px: { xs: 2 } }} className="wrapper-content">
      <Box sx={{ mb: 3 }}>
        <Link component="button" variant="body2" onClick={() => navigate('/support')} sx={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 0.5, mb: 1 }}>
          <ArrowBackIcon fontSize="small" /> חזרה
        </Link>
        <Typography variant="h5" component="h1" sx={{ fontWeight: 600, mb: 1 }}>
          פנייה חדשה
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {attach ? 'מלא את פרטי הבקשה ושלוח כפנייה – נענה בהקדם.' : 'שלח פנייה לתמיכה – נענה בהקדם'}
        </Typography>
      </Box>

      <Paper sx={{ p: 3 }}>
        {error && (
          <Box sx={{ py: 1, mb: 2, bgcolor: 'error.light', color: 'error.contrastText', px: 2, borderRadius: 1 }}>
            {error}
          </Box>
        )}

        <Box className="chat-view-frame" sx={{ width: '100%' }}>
          <Box
            className="message"
            sx={{
              width: '100%',
              bgcolor: 'background.default',
              borderRadius: 1,
              border: '1px solid',
              borderColor: 'divider',
              p: 2,
            }}
          >
            <TextField
              fullWidth
              label="נושא"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              required
              variant="outlined"
              size="small"
              sx={{ mb: 1, '& .MuiOutlinedInput-root': { bgcolor: 'transparent' } }}
            />

            {!attach && (
              <Button
                variant="outlined"
                size="small"
                startIcon={<AddIcon />}
                onClick={() => { setAttach('open'); setSubject((s) => s || 'בקשה לפתיחת אתר'); }}
                sx={{ mb: 2 }}
              >
                הוספת בקשה לפתיחה
              </Button>
            )}

            {(attach === 'open' || attach === 'change') && (
              <Box sx={{ mb: 2, p: 1.5, bgcolor: 'action.hover', borderRadius: 1 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                  <Typography variant="subtitle2">בקשה לפתיחה – תצוגה מקדימה</Typography>
                  <Button size="small" variant="text" color="secondary" onClick={() => { setAttach(null); setUrl(''); setRequestUrl(''); setAction('allow'); setIncludeSubdomains(false); setTags([]); setSubject(''); }}>
                    הסר בקשה
                  </Button>
                </Box>
                {requestUrl && (
                  <TextField fullWidth label="כתובת מלאה" value={requestUrl} disabled size="small" sx={{ mb: 1 }} helperText="הכתובת עם הנתיב שהמשתמש ניסה להיכנס אליה (לצפייה בלבד)" />
                )}
                <TextField fullWidth label="כתובת אתר" value={url} onChange={(e) => handleWebsiteUrlChange(e.target.value)} onPaste={handleWebsiteUrlPaste} size="small" sx={{ mb: 1 }} placeholder="example.com או *.example.com/path או הדבק קישור מלא" helperText="הקלדה חופשית; הדבקת קישור תמלא אוטומטית דומיין + כתובת מלאה" />
                <FormControl fullWidth size="small" sx={{ mb: 1 }}>
                  <InputLabel>פעולה</InputLabel>
                  <Select value={action} label="פעולה" onChange={(e) => setAction(e.target.value as 'allow' | 'block')}>
                    <MenuItem value="allow">אפשר</MenuItem>
                    <MenuItem value="block">חסום</MenuItem>
                  </Select>
                </FormControl>
                <FormControlLabel control={<Checkbox checked={includeSubdomains} onChange={(e) => setIncludeSubdomains(e.target.checked)} />} label="כולל סאב-דומיינים" />
                <Box sx={{ mt: 1 }}>
                  <TagInput value={tags} onChange={setTags} label="תגיות (אופציונלי)" helperText="" />
                </Box>
              </Box>
            )}

            {attach === 'file' && (
              <Box sx={{ mb: 2, p: 1.5, bgcolor: 'action.hover', borderRadius: 1 }}>
                <Typography variant="subtitle2" sx={{ mb: 1 }}>בקשה לפתיחת קובץ – תצוגה מקדימה</Typography>
                <TextField fullWidth label="קישור לקובץ" value={fileUrl} onChange={(e) => setFileUrl(e.target.value)} size="small" sx={{ mb: 1 }} />
                {filename && <TextField fullWidth label="שם הקובץ" value={filename} InputProps={{ readOnly: true }} size="small" sx={{ mb: 1 }} />}
                <TextField fullWidth label="תאר את הקובץ (מה מכיל, סוג, איך פותחים, מאיפה הורדת)" value={fileDescription} onChange={(e) => setFileDescription(e.target.value)} required multiline minRows={3} size="small" />
              </Box>
            )}

            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>אפשר לכתוב בהודעה, לבחור קובץ או להדביק מהלוח</Typography>
            <SupportAttachBar
              onAppendContent={(markdown) => setContent((prev) => (prev ? prev + markdown : markdown.trim()))}
              onUpload={supportApi.uploadFile}
              disabled={submitting}
            />
            <TextField
              fullWidth
              multiline
              minRows={3}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                  e.preventDefault();
                  if (canSubmit && !submitting) handleSubmit();
                }
              }}
              placeholder="כתוב את תוכן הפנייה, או בחר קובץ / הדבק מהלוח"
              variant="outlined"
              size="small"
              sx={{
                mt: 1,
                mb: 1,
                '& .MuiOutlinedInput-root': {
                  bgcolor: 'transparent',
                  minHeight: 80,
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
                onClick={handleSubmit}
                disabled={submitting || !canSubmit}
              >
                {submitting ? 'שולח...' : 'שלח פנייה'}
              </Button>
              <Button variant="outlined" size="small" onClick={() => navigate('/support')}>
                ביטול
              </Button>
            </Box>
          </Box>
        </Box>
      </Paper>
    </Container>
  );
};

export default SupportNewTicketPage;
