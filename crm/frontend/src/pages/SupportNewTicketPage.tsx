/**
 * New support ticket – directly on page (no frame).
 */
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Container,
  Paper,
  Typography,
  Button,
  TextField,
  Link,
} from '@mui/material';
import { ArrowBack as ArrowBackIcon, Send as SendIcon } from '@mui/icons-material';
import { supportApi } from '../api/support';
import SupportAttachBar from '../components/SupportAttachBar';

const SupportNewTicketPage: React.FC = () => {
  const navigate = useNavigate();
  const [subject, setSubject] = useState('');
  const [content, setContent] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async () => {
    setError('');
    if (!subject.trim()) {
      setError('נא להזין נושא');
      return;
    }
    if (!content.trim()) {
      setError('נא להזין תוכן');
      return;
    }
    setSubmitting(true);
    try {
      const ticket = await supportApi.createTicket({
        subject: subject.trim(),
        content: content.trim(),
      });
      navigate(`/support/${ticket.id}`);
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string } } };
      setError(ax?.response?.data?.detail || 'שגיאה ביצירת פנייה');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }} className="wrapper-content">
      <Box sx={{ mb: 3 }}>
        <Link component="button" variant="body2" onClick={() => navigate('/support')} sx={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 0.5, mb: 1 }}>
          <ArrowBackIcon fontSize="small" /> חזרה
        </Link>
        <Typography variant="h5" component="h1" sx={{ fontWeight: 600, mb: 1 }}>
          פנייה חדשה
        </Typography>
        <Typography variant="body2" color="text.secondary">
          שלח פנייה לתמיכה – נענה בהקדם
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
          <SupportAttachBar
            onAppendContent={(markdown) => setContent((prev) => (prev ? prev + markdown : markdown.trim()))}
            onUpload={supportApi.uploadFile}
            disabled={submitting}
          />
          <TextField
            fullWidth
            multiline
            minRows={4}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                e.preventDefault();
                if (subject.trim() && content.trim() && !submitting) handleSubmit();
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
              onClick={handleSubmit}
              disabled={submitting}
            >
              {submitting ? 'שולח...' : 'שלח'}
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
