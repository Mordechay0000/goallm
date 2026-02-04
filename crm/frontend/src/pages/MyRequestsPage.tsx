/**
 * My Requests - User's own rule requests.
 * Submit new requests, view status, manage requests.
 * Supports prefilled URL/params from blocked page redirect.
 */
import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Container,
  Paper,
  Typography,
  Button,
  Box,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Checkbox,
  FormControlLabel,
  Tabs,
  Tab,
  IconButton,
  TablePagination,
} from '@mui/material';
import { Add as AddIcon, Delete as DeleteIcon } from '@mui/icons-material';
import { ruleRequestsApi } from '../api/ruleRequests';
import type { RuleRequest, RuleRequestCreate } from '../api/ruleRequests';
import { TagInput } from '../components/TagInput';
import { validateDomainOrUrl, processUrlInput } from '../utils/validation';

const STATUS_LABELS: Record<string, string> = {
  pending: 'ממתין',
  approved: 'אושר',
  rejected: 'נדחה',
};

const TYPE_LABELS: Record<string, string> = {
  open: 'בקשה לפתיחה',
  change: 'בקשה לשינוי',
};

const MyRequestsPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [requests, setRequests] = useState<RuleRequest[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState(0);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [requestType, setRequestType] = useState<'open' | 'change'>('open');
  const [url, setUrl] = useState('');
  const [urlError, setUrlError] = useState('');
  const [action, setAction] = useState<'allow' | 'block'>('allow');
  const [includeSubdomains, setIncludeSubdomains] = useState(false);
  const [tags, setTags] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);

  const prefilledUrl = searchParams.get('url') || '';
  const prefilledType = searchParams.get('request_type') || '';

  const loadRequests = async () => {
    setLoading(true);
    try {
      const { requests: list, total: t } = await ruleRequestsApi.list({
        page: page + 1,
        page_size: rowsPerPage,
        sort_by: 'created_at',
        sort_order: 'desc',
      });
      setRequests(list);
      setTotal(t);
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string } } };
      console.error(ax?.response?.data?.detail || 'שגיאה בטעינת בקשות');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRequests();
  }, [page, rowsPerPage]);

  useEffect(() => {
    if (prefilledUrl || prefilledType) {
      setDialogOpen(true);
      if (prefilledUrl) {
        try {
          const decoded = decodeURIComponent(prefilledUrl).replace(/^https?:\/\//, '').trim();
          setUrl(decoded);
          setUrlError(validateDomainOrUrl(decoded));
        } catch {
          setUrl(prefilledUrl);
          setUrlError(validateDomainOrUrl(prefilledUrl));
        }
      }
      if (prefilledType === 'open' || prefilledType === 'change') {
        setRequestType(prefilledType);
        setAction(prefilledType === 'open' ? 'allow' : 'block');
      }
    }
  }, [prefilledUrl, prefilledType]);

  const openAddDialog = (type: 'open' | 'change' = 'open') => {
    setRequestType(type);
    setAction(type === 'open' ? 'allow' : 'block');
    setUrl('');
    setUrlError('');
    setIncludeSubdomains(false);
    setTags([]);
    setError('');
    setDialogOpen(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setUrlError('');
    const urlErr = validateDomainOrUrl(url);
    if (urlErr) {
      setUrlError(urlErr);
      return;
    }
    setSubmitting(true);
    try {
      const data: RuleRequestCreate = {
        request_type: requestType,
        url: url.trim(),
        action,
        include_subdomains: includeSubdomains,
        tags: tags.length > 0 ? tags : undefined,
      };
      await ruleRequestsApi.create(data);
      setDialogOpen(false);
      await loadRequests();
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } }; message?: string };
      setError(ax?.response?.data?.detail || ax?.message || 'שגיאה בשליחת הבקשה');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await ruleRequestsApi.delete(id);
      setDeleteConfirm(null);
      await loadRequests();
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } } };
      alert(ax?.response?.data?.detail || 'שגיאה במחיקה');
    }
  };

  const formatDate = (ts: number) => {
    const d = new Date(ts * 1000);
    return d.toLocaleDateString('he-IL') + ' ' + d.toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' });
  };

  const canDelete = (r: RuleRequest) => r.status === 'pending';

  return (
    <Container maxWidth="lg" sx={{ mt: 4 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" gutterBottom>
          הבקשות שלי
        </Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button variant="outlined" startIcon={<AddIcon />} onClick={() => openAddDialog('open')}>
            בקשה לפתיחת אתר
          </Button>
          <Button variant="contained" startIcon={<AddIcon />} onClick={() => openAddDialog('change')}>
            בקשה לשינוי (חסום/פתוח)
          </Button>
        </Box>
      </Box>

      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        שלח בקשות למנהל לאישור. כאן תוכל לראות את סטטוס הבקשות שלך ולנהל אותן.
      </Typography>

      <Paper>
        <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tab label="כל הבקשות" />
        </Tabs>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>תאריך</TableCell>
                <TableCell>סוג</TableCell>
                <TableCell>סטטוס</TableCell>
                <TableCell>כתובת</TableCell>
                <TableCell>פעולה</TableCell>
                <TableCell align="left">פעולות</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                <TableRow><TableCell colSpan={6}>טוען...</TableCell></TableRow>
              ) : requests.length === 0 ? (
                <TableRow><TableCell colSpan={6}>אין בקשות. הוסף בקשה חדשה למעלה.</TableCell></TableRow>
              ) : (
                requests.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell>{formatDate(r.created_at)}</TableCell>
                    <TableCell>{TYPE_LABELS[r.request_type] || r.request_type}</TableCell>
                    <TableCell>
                      <Chip
                        label={STATUS_LABELS[r.status] || r.status}
                        size="small"
                        color={r.status === 'approved' ? 'success' : r.status === 'rejected' ? 'error' : 'default'}
                      />
                    </TableCell>
                    <TableCell>{r.url || (r.domain_pattern || '') + (r.path_pattern || '') || '—'}</TableCell>
                    <TableCell>{r.action || '—'}</TableCell>
                    <TableCell align="left">
                      {canDelete(r) && (
                        <IconButton size="small" color="error" onClick={() => setDeleteConfirm(r.id)} title="מחק">
                          <DeleteIcon />
                        </IconButton>
                      )}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
        {total > 0 && (
          <TablePagination
            component="div"
            count={total}
            page={page}
            onPageChange={(_, p) => setPage(p)}
            rowsPerPage={rowsPerPage}
            onRowsPerPageChange={(e) => { setRowsPerPage(parseInt(e.target.value, 10)); setPage(0); }}
            rowsPerPageOptions={[5, 10, 25, 50]}
            labelRowsPerPage="שורות בעמוד:"
            labelDisplayedRows={({ from, to, count }) => `${from}–${to} מתוך ${count}`}
          />
        )}
      </Paper>

      {/* Add Request Dialog */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>
          {requestType === 'open' ? 'בקשה לפתיחת אתר' : 'בקשה לשינוי (חסום/פתוח)'}
        </DialogTitle>
        <DialogContent>
          <form id="add-request-form" onSubmit={handleSubmit}>
            {error && (
              <Typography color="error" sx={{ mb: 2 }}>{error}</Typography>
            )}
            <TextField
              fullWidth
              label="כתובת אתר"
              value={url}
              onChange={(e) => {
                const { cleaned, setSubdomains } = processUrlInput(e.target.value);
                setUrl(cleaned);
                setUrlError(validateDomainOrUrl(cleaned));
                if (setSubdomains) setIncludeSubdomains(true);
              }}
              placeholder="example.com או *.example.com/path"
              required
              error={!!urlError}
              helperText={urlError || "פרוטוקול ו־*. יוסרו אוטומטית"}
              sx={{ mb: 2, mt: 1 }}
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
              <TagInput value={tags} onChange={setTags} label="תגיות (אופציונלי)" helperText="" />
            </Box>
          </form>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>ביטול</Button>
          <Button
            variant="contained"
            type="submit"
            form="add-request-form"
            disabled={submitting || !url.trim() || !!urlError}
          >
            {submitting ? 'שולח...' : 'שלח בקשה'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete confirmation */}
      <Dialog open={deleteConfirm !== null} onClose={() => setDeleteConfirm(null)}>
        <DialogTitle>מחיקת בקשה</DialogTitle>
        <DialogContent>למחוק את הבקשה?</DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteConfirm(null)}>ביטול</Button>
          <Button color="error" variant="contained" onClick={() => deleteConfirm !== null && handleDelete(deleteConfirm)}>
            מחק
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default MyRequestsPage;
