/**
 * My Requests - User's own rule requests.
 * Submit new requests, view status, manage requests.
 * Supports prefilled URL/params from blocked page redirect.
 */
import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
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
  TableSortLabel,
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
  InputAdornment,
} from '@mui/material';
import { Add as AddIcon, Delete as DeleteIcon, Search as SearchIcon } from '@mui/icons-material';
import { ruleRequestsApi } from '../api/ruleRequests';
import type { RuleRequest, RuleRequestCreate } from '../api/ruleRequests';
import { TagInput } from '../components/TagInput';
import { validateDomainOrUrl, processUrlInput } from '../utils/validation';
import { PAGE_DESCRIPTIONS, EMPTY_STATE, PLACEHOLDERS } from '../brand';

const STATUS_LABELS: Record<string, string> = {
  pending: 'ממתין',
  approved: 'אושר',
  rejected: 'נדחה',
};

const TYPE_LABELS: Record<string, string> = {
  open: 'בקשה לפתיחה',
  change: 'בקשה לשינוי',
  file: 'פתיחת קובץ',
};

type SortBy = 'created_at' | 'request_type' | 'status' | 'url';
type SortOrder = 'asc' | 'desc';

const MyRequestsPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [requests, setRequests] = useState<RuleRequest[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState(0);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [sortBy, setSortBy] = useState<SortBy>('created_at');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [typeFilter, setTypeFilter] = useState<string>('');
  const [search, setSearch] = useState('');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [requestType] = useState<'open' | 'change'>('open');
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
      const params: Record<string, string | number> = {
        page: page + 1,
        page_size: rowsPerPage,
        sort_by: sortBy,
        sort_order: sortOrder,
      };
      if (statusFilter) params.status_filter = statusFilter;
      if (typeFilter) params.request_type_filter = typeFilter;
      if (search.trim()) params.search = search.trim();
      const { requests: list, total: t } = await ruleRequestsApi.list(params);
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
    // eslint-disable-next-line react-hooks/exhaustive-deps -- loadRequests reads filter/sort/page state
  }, [page, rowsPerPage, sortBy, sortOrder, statusFilter, typeFilter, search]);

  const handleSort = (col: SortBy) => {
    const isAsc = sortBy === col && sortOrder === 'asc';
    setSortOrder(isAsc ? 'desc' : 'asc');
    setSortBy(col);
    setPage(0);
  };

  // כל יצירת בקשה עוברת דרך מערכת הפניות
  useEffect(() => {
    if ((prefilledType === 'open' || prefilledType === 'change') && navigate) {
      const params = new URLSearchParams();
      params.set('attach', prefilledType);
      if (prefilledUrl) params.set('url', prefilledUrl);
      navigate(`/support/new?${params.toString()}`, { replace: true });
    }
  }, [prefilledType, prefilledUrl, navigate]);

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
    <Container maxWidth="lg" sx={{ mb: 4 }} className="page-section container-content">
      <Box className="page-title-section" sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 2, mb: 3 }}>
        <Box>
          <Typography variant="h5" component="h1" sx={{ fontWeight: 600, mb: 1 }}>
            בקשות ששלחתי
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {PAGE_DESCRIPTIONS.requests}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button variant="outlined" startIcon={<AddIcon />} onClick={() => navigate('/support/new?attach=open')}>
            בקשה לפתיחת אתר
          </Button>
          <Button variant="contained" startIcon={<AddIcon />} onClick={() => navigate('/support/new?attach=change')}>
            בקשה לשינוי (חסום/פתוח)
          </Button>
        </Box>
      </Box>

      <Paper className="paper-table">
        <Box className="card-header-accent spectrum-alt2" sx={{ px: 2, pt: 2, pb: 1 }}>
          <Typography className="section-title">רשימת בקשות</Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center', p: 2, borderBottom: 1, borderColor: 'divider' }}>
          <TextField
            size="small"
            placeholder={PLACEHOLDERS.search}
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(0); }}
            sx={{ minWidth: 180 }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
            }}
          />
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>סטטוס</InputLabel>
            <Select value={statusFilter} label="סטטוס" onChange={(e) => { setStatusFilter(e.target.value); setPage(0); }}>
              <MenuItem value="">הכל</MenuItem>
              <MenuItem value="pending">ממתין</MenuItem>
              <MenuItem value="approved">אושר</MenuItem>
              <MenuItem value="rejected">נדחה</MenuItem>
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel>סוג בקשה</InputLabel>
            <Select value={typeFilter} label="סוג בקשה" onChange={(e) => { setTypeFilter(e.target.value); setPage(0); }}>
              <MenuItem value="">הכל</MenuItem>
              <MenuItem value="open">בקשה לפתיחה</MenuItem>
              <MenuItem value="change">בקשה לשינוי</MenuItem>
            </Select>
          </FormControl>
        </Box>
        <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tab label="כל הבקשות" />
        </Tabs>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell align="left" sortDirection={sortBy === 'created_at' ? sortOrder : false}>
                  <TableSortLabel active={sortBy === 'created_at'} direction={sortBy === 'created_at' ? sortOrder : 'asc'} onClick={() => handleSort('created_at')}>
                    תאריך
                  </TableSortLabel>
                </TableCell>
                <TableCell align="center" sortDirection={sortBy === 'request_type' ? sortOrder : false}>
                  <TableSortLabel active={sortBy === 'request_type'} direction={sortBy === 'request_type' ? sortOrder : 'asc'} onClick={() => handleSort('request_type')}>
                    סוג
                  </TableSortLabel>
                </TableCell>
                <TableCell align="center" sortDirection={sortBy === 'status' ? sortOrder : false}>
                  <TableSortLabel active={sortBy === 'status'} direction={sortBy === 'status' ? sortOrder : 'asc'} onClick={() => handleSort('status')}>
                    סטטוס
                  </TableSortLabel>
                </TableCell>
                <TableCell align="right">כתובת</TableCell>
                <TableCell align="center">פעולה</TableCell>
                <TableCell align="center">פעולות</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                <TableRow><TableCell colSpan={6}>טוען...</TableCell></TableRow>
              ) : requests.length === 0 ? (
                <TableRow><TableCell colSpan={6}>{EMPTY_STATE.noRequests}</TableCell></TableRow>
              ) : (
                requests.map((r) => (
                  <TableRow key={r.id} hover sx={{ '&:hover': { bgcolor: 'action.selected' } }}>
                    <TableCell align="left">{formatDate(r.created_at)}</TableCell>
                    <TableCell align="center">{TYPE_LABELS[r.request_type] || r.request_type}</TableCell>
                    <TableCell align="center">
                      <Chip
                        label={STATUS_LABELS[r.status] || r.status}
                        size="small"
                        variant="outlined"
                        color={r.status === 'approved' ? 'secondary' : r.status === 'rejected' ? 'error' : 'default'}
                      />
                    </TableCell>
                    <TableCell
                      align="right"
                      sx={{
                        maxWidth: 400,
                        overflowX: 'auto',
                        whiteSpace: 'nowrap',
                        scrollbarWidth: 'thin',
                        scrollbarColor: '#1e3a5f #e2e8f0',
                        '&::-webkit-scrollbar': { height: 8 },
                        '&::-webkit-scrollbar-track': { background: '#e2e8f0', borderRadius: 8 },
                        '&::-webkit-scrollbar-thumb': { background: '#1e3a5f', borderRadius: 8, border: '2px solid #e2e8f0' },
                        '&::-webkit-scrollbar-thumb:hover': { background: '#152a45' },
                      }}
                    >
                      {r.url || (r.domain_pattern || '') + (r.path_pattern || '') || '—'}
                    </TableCell>
                    <TableCell align="center">{r.action || '—'}</TableCell>
                    <TableCell align="center">
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
