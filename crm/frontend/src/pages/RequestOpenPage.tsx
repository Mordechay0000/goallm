/**
 * Request to open a site - form like add rule, submits as rule request (open).
 * Link from "send for review" page: /request-open?url=...
 */
import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  Container,
  Paper,
  Typography,
  Button,
  Box,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Checkbox,
  FormControlLabel,
  Alert,
} from '@mui/material';
import { ArrowBack as ArrowBackIcon } from '@mui/icons-material';
import { ruleRequestsApi } from '../api/ruleRequests';
import { TagInput } from '../components/TagInput';

const RequestOpenPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const urlFromQuery = searchParams.get('url') || '';
  const actionFromQuery = searchParams.get('action') || 'allow';
  const includeSubdomainsFromQuery = searchParams.get('include_subdomains') || '';
  const tagsFromQuery = searchParams.get('tags') || '';
  const [url, setUrl] = useState('');
  const [action, setAction] = useState<'allow' | 'block'>('allow');
  const [includeSubdomains, setIncludeSubdomains] = useState(false);
  const [tags, setTags] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    if (urlFromQuery) {
      try {
        const decoded = decodeURIComponent(urlFromQuery);
        setUrl(decoded.replace(/^https?:\/\//, '').trim());
      } catch {
        setUrl(urlFromQuery);
      }
    }
    if (actionFromQuery === 'allow' || actionFromQuery === 'block') setAction(actionFromQuery);
    if (includeSubdomainsFromQuery === '1' || includeSubdomainsFromQuery.toLowerCase() === 'true') setIncludeSubdomains(true);
    if (tagsFromQuery) setTags(tagsFromQuery.split(',').map((t) => t.trim()).filter(Boolean));
  }, [urlFromQuery, actionFromQuery, includeSubdomainsFromQuery, tagsFromQuery]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!url.trim()) {
      setError('נא להזין כתובת');
      return;
    }
    setLoading(true);
    try {
      await ruleRequestsApi.create({
        request_type: 'open',
        url: url.trim(),
        action,
        include_subdomains: includeSubdomains,
        tags: tags.length > 0 ? tags : undefined,
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
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/profiles')}>
          חזרה לפרופילים
        </Button>
      </Container>
    );
  }

  return (
    <Container maxWidth="sm" sx={{ mt: 4, mb: 4 }}>
      <Button startIcon={<ArrowBackIcon />} onClick={() => navigate(-1)} sx={{ mb: 2 }}>
        חזרה
      </Button>
      <Typography variant="h5" gutterBottom>
        בקשה לפתיחת אתר
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        מלא את הפרטים והבקשה תישלח למנהל לאישור.
      </Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      <Paper sx={{ p: 4 }}>
        <form onSubmit={handleSubmit}>
          <TextField
            fullWidth
            label="כתובת אתר"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="example.com או *.example.com/path"
            required
            sx={{ mb: 2 }}
          />
          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>פעולה</InputLabel>
            <Select value={action} label="פעולה" onChange={(e) => setAction(e.target.value as 'allow' | 'block')}>
              <MenuItem value="allow">אפשר</MenuItem>
              <MenuItem value="block">חסום</MenuItem>
            </Select>
          </FormControl>
          <FormControlLabel
            control={<Checkbox checked={includeSubdomains} onChange={(e) => setIncludeSubdomains(e.target.checked)} />}
            label="כולל סאב-דומיינים"
            sx={{ mb: 2 }}
          />
          <Box sx={{ mb: 2 }}>
            <TagInput
              value={tags}
              onChange={setTags}
              label="תגיות (אופציונלי)"
              helperText=""
            />
          </Box>
          <Button type="submit" variant="contained" fullWidth disabled={loading}>
            {loading ? 'שולח...' : 'שלח בקשה'}
          </Button>
        </form>
      </Paper>
    </Container>
  );
};

export default RequestOpenPage;
