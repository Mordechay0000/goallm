/**
 * Request to open a file - from file download send-for-review flow.
 * Link: /request-file?file_url=...&filename=...
 * Title: פתיחת קובץ – {filename}. User must describe the file (content, type, how to open, source).
 */
import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  Container,
  Paper,
  Typography,
  Button,
  TextField,
  Alert,
  Box,
} from '@mui/material';
import { ArrowBack as ArrowBackIcon } from '@mui/icons-material';
import { ruleRequestsApi } from '../api/ruleRequests';

const RequestFilePage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const fileUrlFromQuery = searchParams.get('file_url') || '';
  const filenameFromQuery = searchParams.get('filename') || '';
  const [fileUrl, setFileUrl] = useState('');
  const [filename, setFilename] = useState('');
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    if (fileUrlFromQuery) {
      try {
        setFileUrl(decodeURIComponent(fileUrlFromQuery).trim());
      } catch {
        setFileUrl(fileUrlFromQuery);
      }
    }
    if (filenameFromQuery) {
      try {
        setFilename(decodeURIComponent(filenameFromQuery).trim());
      } catch {
        setFilename(filenameFromQuery);
      }
    }
  }, [fileUrlFromQuery, filenameFromQuery]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!fileUrl.trim()) {
      setError('חסר קישור לקובץ');
      return;
    }
    if (!description.trim()) {
      setError('נא לתאר את הקובץ (מה הוא מכיל, סוג, איך פותחים, מאיפה הורדת)');
      return;
    }
    setLoading(true);
    try {
      await ruleRequestsApi.create({
        request_type: 'file',
        url: fileUrl.trim(),
        notes: description.trim(),
      });
      setSuccess(true);
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } }; message?: string };
      setError(ax?.response?.data?.detail || ax?.message || 'שגיאה בשליחת הבקשה');
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <Container maxWidth="sm" sx={{ mt: 4, mb: 4 }}>
        <Alert severity="success" sx={{ mb: 2 }}>
          הבקשה נשלחה. מנהל יבדוק ויאשר או ידחה.
        </Alert>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/profiles')} color="secondary" variant="outlined">
          חזרה לפרופילים
        </Button>
      </Container>
    );
  }

  const displayFilename = filename || 'קובץ';

  return (
    <Container maxWidth="sm" sx={{ mt: 4, mb: 4 }}>
      <Button startIcon={<ArrowBackIcon />} onClick={() => navigate(-1)} color="secondary" variant="outlined" sx={{ mb: 2 }}>
        חזרה
      </Button>
      <Typography variant="h5" gutterBottom>
        פתיחת קובץ – {displayFilename}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        נא לתאר את הקובץ כדי שנוכל לבדוק אותו. אחרי האישור ניתן יהיה לפתוח קבצים מסוג זה.
      </Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      <Paper sx={{ p: 4 }}>
        <Box className="card-header-accent" sx={{ mb: 3 }}>
          <Typography variant="h6">נא לשלוח לבדיקה</Typography>
        </Box>
        <form onSubmit={handleSubmit}>
          <TextField
            fullWidth
            label="קישור לקובץ"
            value={fileUrl}
            onChange={(e) => setFileUrl(e.target.value)}
            required
            sx={{ mb: 2 }}
          />
          {filename && (
            <TextField
              fullWidth
              label="שם הקובץ"
              value={filename}
              InputProps={{ readOnly: true }}
              sx={{ mb: 2 }}
            />
          )}
          <TextField
            fullWidth
            label="תאר את הקובץ"
            placeholder="מה הקובץ מכיל, מה הסוג, איך פותחים אותו, מאיפה הורדת וכו'"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            required
            multiline
            minRows={4}
            sx={{ mb: 2 }}
          />
          <Box sx={{ mt: 2 }}>
            <Button type="submit" variant="contained" color="secondary" fullWidth disabled={loading}>
              {loading ? 'שולח...' : 'שלח לבדיקה'}
            </Button>
          </Box>
        </form>
      </Paper>
    </Container>
  );
};

export default RequestFilePage;
