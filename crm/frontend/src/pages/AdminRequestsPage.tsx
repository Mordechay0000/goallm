/**
 * Admin: list all rule requests with filters, sort, edit, approve/reject/delete.
 * Row click: approved → rules page; pending/rejected → edit dialog.
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Container,
  Divider,
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
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  IconButton,
  InputAdornment,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Checkbox,
  FormControlLabel,
  Menu,
  ListItemIcon,
  ListItemText,
  TableSortLabel,
  TablePagination,
  TextField,
} from '@mui/material';
import { Check as CheckIcon, Close as CloseIcon, Delete as DeleteIcon, Edit as EditIcon, MoreVert as MoreVertIcon, Search as SearchIcon } from '@mui/icons-material';
import { ruleRequestsApi } from '../api/ruleRequests';
import type { RuleRequest, RuleRequestUpdate } from '../api/ruleRequests';
import { adminApi } from '../api/admin';
import { TagInput } from '../components/TagInput';
import { validateDomainOrUrl, processUrlInput, normalizeUrlForRule, WWW_NORMALIZED_MESSAGE } from '../utils/validation';
import { PAGE_DESCRIPTIONS, PLACEHOLDERS } from '../brand';

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

type RequestOrder = 'asc' | 'desc';
type RequestSortBy = 'created_at' | 'request_type' | 'status' | 'user_id';
const ROWS_PER_PAGE_OPTIONS = [10, 25, 50, 100];

const AdminRequestsPage: React.FC = () => {
  const navigate = useNavigate();
  const [requests, setRequests] = useState<RuleRequest[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [requestTypeFilter, setRequestTypeFilter] = useState<string>('');
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<RequestSortBy>('created_at');
  const [sortOrder, setSortOrder] = useState<RequestOrder>('desc');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [approveDialog, setApproveDialog] = useState<RuleRequest | null>(null);
  const [editDialog, setEditDialog] = useState<RuleRequest | null>(null);
  const [editUrl, setEditUrl] = useState('');
  const [editUrlError, setEditUrlError] = useState('');
  const [editAction, setEditAction] = useState<'allow' | 'block'>('block');
  const [editIncludeSubdomains, setEditIncludeSubdomains] = useState(false);
  const [editTags, setEditTags] = useState<string[]>([]);
  const [editTextFilterEnabled, setEditTextFilterEnabled] = useState(true);
  const [editImageFilterEnabled, setEditImageFilterEnabled] = useState(true);
  const [editFileFilterEnabled, setEditFileFilterEnabled] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editMoreAnchor, setEditMoreAnchor] = useState<null | HTMLElement>(null);

  const loadRequests = async () => {
    setLoading(true);
    try {
      const params: Record<string, string | number> = {
        sort_by: sortBy,
        sort_order: sortOrder,
        page: page + 1,
        page_size: rowsPerPage,
      };
      if (statusFilter) params.status_filter = statusFilter;
      if (requestTypeFilter) params.request_type_filter = requestTypeFilter;
      if (search.trim()) params.search = search.trim();
      const { requests: list, total: t } = await ruleRequestsApi.list(params);
      setRequests(list);
      setTotal(t);
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string } } };
      alert(ax?.response?.data?.detail || 'שגיאה בטעינת בקשות');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRequests();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- loadRequests reads filter/sort/page state
  }, [statusFilter, requestTypeFilter, search, sortBy, sortOrder, page, rowsPerPage]);

  const handleSort = (col: RequestSortBy) => {
    const isAsc = sortBy === col && sortOrder === 'asc';
    setSortOrder(isAsc ? 'desc' : 'asc');
    setSortBy(col);
    setPage(0);
  };

  const handleChangePage = (_: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (e: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(e.target.value, 10));
    setPage(0);
  };

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearch(e.target.value);
    setPage(0);
  };

  const handleApproveClick = (req: RuleRequest) => {
    setApproveDialog(req);
  };

  const handleApproveConfirm = async () => {
    if (!approveDialog) return;
    try {
      await ruleRequestsApi.approve(approveDialog.id);
      setApproveDialog(null);
      await loadRequests();
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string } } };
      alert(ax?.response?.data?.detail || 'שגיאה באישור');
    }
  };

  const handleReject = async (req: RuleRequest) => {
    if (!confirm('לאשר דחיית הבקשה?')) return;
    try {
      await ruleRequestsApi.reject(req.id);
      loadRequests();
      setEditDialog(null);
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string } } };
      alert(ax?.response?.data?.detail || 'שגיאה בדחייה');
    }
  };

  const handleDelete = async (req: RuleRequest, e?: React.MouseEvent) => {
    e?.stopPropagation();
    if (!confirm('למחוק את הבקשה?')) return;
    try {
      await ruleRequestsApi.delete(req.id);
      loadRequests();
      setEditDialog(null);
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } } };
      alert(ax?.response?.data?.detail || 'שגיאה במחיקה');
    }
  };

  const openEditDialog = (req: RuleRequest) => {
    setEditDialog(req);
    const u = req.url || (req.domain_pattern || '') + (req.path_pattern || '') || '';
    setEditUrl(u);
    setEditUrlError(validateDomainOrUrl(u));
    setEditAction((req.action as 'allow' | 'block') || 'block');
    setEditIncludeSubdomains(!!req.include_subdomains);
    setEditTags(normalizeTags(req.tags));
    if (req.request_type !== 'file') {
      setEditTextFilterEnabled((req as { text_filter_enabled?: boolean }).text_filter_enabled !== false);
      setEditImageFilterEnabled((req as { image_filter_enabled?: boolean }).image_filter_enabled !== false);
      setEditFileFilterEnabled((req as { file_filter_enabled?: boolean }).file_filter_enabled !== false);
    }
    if (req.approved_rule_id) {
      adminApi.getGlobalRule(req.approved_rule_id).then((rule) => {
        const ruleUrl = (rule.domain_pattern || '') + (rule.path_pattern || '/');
        setEditUrl(ruleUrl);
        setEditUrlError(validateDomainOrUrl(ruleUrl));
        setEditAction((rule.action as 'allow' | 'block') || 'allow');
        setEditIncludeSubdomains(!!rule.include_subdomains);
        setEditTags(normalizeTags(rule.tags));
        setEditTextFilterEnabled(rule.text_filter_enabled !== false);
        setEditImageFilterEnabled(rule.image_filter_enabled !== false);
        setEditFileFilterEnabled(rule.file_filter_enabled !== false);
      }).catch(() => {});
    }
  };

  const normalizeTags = (tags: unknown): string[] => {
    if (Array.isArray(tags)) return tags.filter((t): t is string => typeof t === 'string');
    if (typeof tags === 'string') {
      try {
        const parsed = JSON.parse(tags);
        return Array.isArray(parsed) ? parsed.filter((t: unknown): t is string => typeof t === 'string') : tags.split(',').map((s: string) => s.trim()).filter(Boolean);
      } catch {
        return tags.split(',').map((s: string) => s.trim()).filter(Boolean);
      }
    }
    return [];
  };

  const handleRowClick = (req: RuleRequest) => {
    if (req.status === 'approved') {
      if (req.approved_rule_id) navigate(`/admin/global-rules?edit=${req.approved_rule_id}`);
      else if (req.approved_profile_id) navigate(`/profiles/${req.approved_profile_id}/rules`);
      else navigate('/admin/global-rules');
      return;
    }
    if (req.status === 'pending' || req.status === 'rejected') {
      openEditDialog(req);
    }
  };

  const saveEditThenOpenApprove = async () => {
    if (!editDialog) return;
    const { normalized, hadWww } = normalizeUrlForRule(editUrl);
    const err = validateDomainOrUrl(normalized);
    if (err) {
      setEditUrlError(err);
      return;
    }
    setSaving(true);
    try {
      const data: RuleRequestUpdate = {
        url: normalized,
        action: editAction,
        include_subdomains: editIncludeSubdomains,
        tags: editTags.length > 0 ? editTags : undefined,
        text_filter_enabled: editTextFilterEnabled,
        image_filter_enabled: editImageFilterEnabled,
        file_filter_enabled: editFileFilterEnabled,
      };
      await ruleRequestsApi.update(editDialog.id, data);
      const reqToApprove = { ...editDialog, ...data };
      setEditDialog(null);
      await loadRequests();
      setApproveDialog(reqToApprove);
      if (hadWww) alert(WWW_NORMALIZED_MESSAGE);
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string } } };
      alert(ax?.response?.data?.detail || 'שגיאה בשמירה');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveEdit = async () => {
    if (!editDialog) return;
    const { normalized, hadWww } = normalizeUrlForRule(editUrl);
    if (editDialog.request_type !== 'file') {
      const err = validateDomainOrUrl(normalized);
      if (err) {
        setEditUrlError(err);
        return;
      }
    }
    setSaving(true);
    try {
      if (editDialog.approved_rule_id) {
        await adminApi.updateGlobalRule(editDialog.approved_rule_id, {
          url: normalized,
          action: editAction,
          include_subdomains: editIncludeSubdomains,
          tags: editTags.length > 0 ? editTags : undefined,
          text_filter_enabled: editTextFilterEnabled,
          image_filter_enabled: editImageFilterEnabled,
          file_filter_enabled: editFileFilterEnabled,
        });
      } else {
        const data: RuleRequestUpdate = {
          url: normalized,
          action: editAction,
          include_subdomains: editIncludeSubdomains,
          tags: editTags.length > 0 ? editTags : undefined,
          text_filter_enabled: editTextFilterEnabled,
          image_filter_enabled: editImageFilterEnabled,
          file_filter_enabled: editFileFilterEnabled,
        };
        await ruleRequestsApi.update(editDialog.id, data);
      }
      setEditDialog(null);
      await loadRequests();
      if (hadWww) alert(WWW_NORMALIZED_MESSAGE);
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string } } };
      alert(ax?.response?.data?.detail || 'שגיאה בשמירה');
    } finally {
      setSaving(false);
    }
  };

  const formatDate = (ts: number) => {
    const d = new Date(ts * 1000);
    return d.toLocaleDateString('he-IL') + ' ' + d.toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <Container maxWidth="lg" sx={{ mb: 4, px: { xs: 0 } }} className="page-section container-content">
      <Box className="page-title-section" sx={{ mb: 3 }}>
        <Typography variant="h5" component="h1" sx={{ fontWeight: 600, mb: 1 }}>
          בקשות שהתקבלו
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {PAGE_DESCRIPTIONS.adminRequests}
        </Typography>
      </Box>

      <Paper sx={{ p: { xs: 2, sm: 2 }, mb: 2 }}>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center' }}>
          <TextField
            size="small"
            fullWidth
            placeholder={PLACEHOLDERS.search}
            value={search}
            onChange={handleSearchChange}
            sx={{ minWidth: { xs: '100%', sm: 220 } }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" color="action" />
                </InputAdornment>
              ),
            }}
          />
          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel>סוג בקשה</InputLabel>
            <Select
              value={requestTypeFilter}
              label="סוג בקשה"
              onChange={(e) => { setRequestTypeFilter(e.target.value); setPage(0); }}
            >
              <MenuItem value="">הכל</MenuItem>
              <MenuItem value="open">בקשה לפתיחה</MenuItem>
              <MenuItem value="change">בקשה לשינוי</MenuItem>
              <MenuItem value="file">פתיחת קובץ</MenuItem>
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>סטטוס</InputLabel>
            <Select value={statusFilter} label="סטטוס" onChange={(e) => { setStatusFilter(e.target.value); setPage(0); }}>
              <MenuItem value="">הכל</MenuItem>
              <MenuItem value="pending">ממתין</MenuItem>
              <MenuItem value="approved">אושר</MenuItem>
              <MenuItem value="rejected">נדחה</MenuItem>
            </Select>
          </FormControl>
        </Box>
      </Paper>

      {loading && requests.length === 0 ? (
        <Typography>טוען...</Typography>
      ) : (
        <>
          <Divider sx={{ my: 2 }} />
          <Paper className="paper-table">
            <Box className="card-header-accent" sx={{ px: 2, pt: 2, pb: 1 }}>
              <Typography className="section-title">בקשות שהתקבלו</Typography>
            </Box>
            <Divider sx={{ mx: 2 }} />
            <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sortDirection={sortBy === 'created_at' ? sortOrder : false}>
                    <TableSortLabel active={sortBy === 'created_at'} direction={sortBy === 'created_at' ? sortOrder : 'asc'} onClick={() => handleSort('created_at')}>
                      תאריך
                    </TableSortLabel>
                  </TableCell>
                  <TableCell sortDirection={sortBy === 'request_type' ? sortOrder : false}>
                    <TableSortLabel active={sortBy === 'request_type'} direction={sortBy === 'request_type' ? sortOrder : 'asc'} onClick={() => handleSort('request_type')}>
                      סוג
                    </TableSortLabel>
                  </TableCell>
                  <TableCell sortDirection={sortBy === 'status' ? sortOrder : false}>
                    <TableSortLabel active={sortBy === 'status'} direction={sortBy === 'status' ? sortOrder : 'asc'} onClick={() => handleSort('status')}>
                      סטטוס
                    </TableSortLabel>
                  </TableCell>
                  <TableCell>משתמש</TableCell>
                  <TableCell>כתובת / דומיין</TableCell>
                  <TableCell>פעולה</TableCell>
                  <TableCell align="left">פעולות</TableCell>
                </TableRow>
              </TableHead>
            <TableBody>
              {requests.map((r) => (
                <TableRow
                  key={r.id}
                  hover
                  sx={{
                    cursor: r.status === 'approved' || r.status === 'pending' || r.status === 'rejected' ? 'pointer' : 'default',
                    '&:hover': { bgcolor: 'action.selected' },
                  }}
                  onClick={() => handleRowClick(r)}
                >
                  <TableCell>{formatDate(r.created_at)}</TableCell>
                  <TableCell>{TYPE_LABELS[r.request_type] || r.request_type}</TableCell>
                  <TableCell>
                    <Chip
                      label={STATUS_LABELS[r.status] || r.status}
                      size="small"
                      variant="outlined"
                      color={r.status === 'approved' ? 'secondary' : r.status === 'rejected' ? 'error' : 'default'}
                    />
                  </TableCell>
                  <TableCell>{r.user_phone ?? (r.user_id ? '—' : 'מעמוד חסום')}</TableCell>
                  <TableCell
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
                  <TableCell>{r.action || '—'}</TableCell>
                  <TableCell align="left" onClick={(e) => e.stopPropagation()}>
                    {r.status === 'pending' && (
                      <>
                        <Button size="small" color="secondary" startIcon={<CheckIcon />} onClick={() => handleApproveClick(r)}>אשר</Button>
                        <Button size="small" color="error" startIcon={<CloseIcon />} onClick={() => handleReject(r)}>דחה</Button>
                        <Button size="small" color="secondary" variant="outlined" startIcon={<EditIcon />} onClick={() => openEditDialog(r)}>עריכה</Button>
                        <IconButton size="small" onClick={(e) => handleDelete(r, e)} title="מחק"><DeleteIcon /></IconButton>
                      </>
                    )}
                    {r.status === 'rejected' && (
                      <>
                        <Button size="small" color="secondary" startIcon={<CheckIcon />} onClick={() => handleApproveClick(r)}>אשר</Button>
                        <Button size="small" color="secondary" variant="outlined" startIcon={<EditIcon />} onClick={() => openEditDialog(r)}>עריכה</Button>
                        <IconButton size="small" onClick={(e) => handleDelete(r, e)} title="מחק"><DeleteIcon /></IconButton>
                      </>
                    )}
                    {r.status === 'approved' && (
                      <>
                        {r.approved_rule_id != null && (
                          <Button size="small" color="secondary" variant="outlined" startIcon={<EditIcon />} onClick={(e) => { e.stopPropagation(); openEditDialog(r); }}>עריכת כלל</Button>
                        )}
                        <Button size="small" color="secondary" variant="outlined" startIcon={<EditIcon />} onClick={(e) => { e.stopPropagation(); if (r.approved_rule_id) navigate(`/admin/global-rules?edit=${r.approved_rule_id}`); else if (r.approved_profile_id) navigate(`/profiles/${r.approved_profile_id}/rules`); else navigate('/admin/global-rules'); }}>לכלל</Button>
                        <IconButton size="small" onClick={(e) => handleDelete(r, e)} title="מחק"><DeleteIcon /></IconButton>
                      </>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          </TableContainer>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 2, px: 2, py: 1 }}>
              <TablePagination
                component="div"
                count={total}
                page={page}
                onPageChange={handleChangePage}
                rowsPerPage={rowsPerPage}
                onRowsPerPageChange={handleChangeRowsPerPage}
                rowsPerPageOptions={ROWS_PER_PAGE_OPTIONS}
                labelRowsPerPage="שורות בעמוד:"
                labelDisplayedRows={({ from, to, count }) => `${from}–${to} מתוך ${count !== -1 ? count : `יותר מ־${to}`}`}
              />
              {total > rowsPerPage && (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <Typography variant="body2" color="text.secondary">עבור לעמוד:</Typography>
                  <TextField
                    type="number"
                    size="small"
                    value={page + 1}
                    onChange={(e) => {
                      const v = parseInt(e.target.value, 10);
                      if (!Number.isNaN(v)) setPage(Math.min(Math.max(0, v - 1), Math.ceil(total / rowsPerPage) - 1));
                    }}
                    inputProps={{ min: 1, max: Math.ceil(total / rowsPerPage) || 1 }}
                    sx={{ width: 56 }}
                  />
                </Box>
              )}
            </Box>
          </Paper>
        </>
      )}

      {/* Approve: adds rule to global list (or for file requests just marks as approved) */}
      <Dialog open={!!approveDialog} onClose={() => setApproveDialog(null)}>
        <DialogTitle>
          {approveDialog?.request_type === 'file' ? 'אישור בקשת פתיחת קובץ' : 'אישור בקשה – הכלל יווסף לרשימה הגלובלית'}
        </DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            {approveDialog?.request_type === 'file'
              ? 'אישור הבקשה יסומן כ־אושר. לא נוצר כלל ברשימה.'
              : 'אישור הבקשה יוסיף את הכלל לרשימה הגלובלית (רשימה לבנה בסיסית). רק אדמין יכול לערוך את הרשימה הגלובלית.'}
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setApproveDialog(null)}>ביטול</Button>
          <Button variant="contained" onClick={handleApproveConfirm}>אישור</Button>
        </DialogActions>
      </Dialog>

      {/* Edit dialog */}
      <Dialog open={!!editDialog} onClose={() => setEditDialog(null)} maxWidth="sm" fullWidth>
        <DialogTitle>{editDialog?.status === 'rejected' ? 'עריכת בקשה (נדחה)' : 'עריכת בקשה'}</DialogTitle>
        <DialogContent>
          {editDialog && (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
              {(editDialog.status === 'approved' || editDialog.status === 'rejected') && (editDialog.resolved_by_name != null || editDialog.updated_at != null) && (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, pb: 1, borderBottom: 1, borderColor: 'divider' }}>
                  {editDialog.resolved_by_name != null && (
                    <Typography variant="body2" color="text.secondary">
                      {editDialog.status === 'approved' ? 'אושר על ידי:' : 'נדחה על ידי:'} {editDialog.resolved_by_name}
                    </Typography>
                  )}
                  {editDialog.updated_at != null && (
                    <Typography variant="body2" color="text.secondary">
                      עדכון אחרון: {formatDate(editDialog.updated_at)}
                    </Typography>
                  )}
                </Box>
              )}
              <TextField
                fullWidth
                label={editDialog.request_type === 'file' ? 'קישור לקובץ' : 'כתובת מלאה (לא לעריכה)'}
                value={editDialog.request_url || editDialog.url || (editDialog.domain_pattern || '') + (editDialog.path_pattern || '') || '—'}
                InputProps={{ readOnly: true }}
                sx={{ '& .MuiInputBase-input': { color: 'text.secondary', bgcolor: 'action.hover' } }}
                size="small"
              />
              {editDialog.request_type === 'file' && editDialog.notes && (
                <TextField
                  fullWidth
                  label="תיאור הקובץ (מהמשתמש)"
                  value={editDialog.notes}
                  InputProps={{ readOnly: true }}
                  multiline
                  minRows={2}
                  size="small"
                />
              )}
              {editDialog.request_type !== 'file' && (
              <>
              <TextField
                fullWidth
                label="כתובת אתר"
                value={editUrl}
                onChange={(e) => {
                  const { cleaned, setSubdomains } = processUrlInput(e.target.value);
                  setEditUrl(cleaned);
                  setEditUrlError(validateDomainOrUrl(cleaned));
                  if (setSubdomains) setEditIncludeSubdomains(true);
                }}
                placeholder="example.com או *.example.com/path"
                error={!!editUrlError}
                helperText={editUrlError || "פרוטוקול ו־*. יוסרו אוטומטית"}
              />
              <FormControl fullWidth>
                <InputLabel>פעולה</InputLabel>
                <Select value={editAction} label="פעולה" onChange={(e) => setEditAction(e.target.value as 'allow' | 'block')}>
                  <MenuItem value="allow">אפשר</MenuItem>
                  <MenuItem value="block">חסום</MenuItem>
                </Select>
              </FormControl>
              <FormControlLabel control={<Checkbox checked={editIncludeSubdomains} onChange={(e) => setEditIncludeSubdomains(e.target.checked)} />} label="כולל סאב-דומיינים" />
              <TagInput value={editTags} onChange={setEditTags} label="תגיות" helperText="" />
              {editAction === 'allow' && (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, pt: 0.5 }}>
                  <Typography variant="subtitle2" color="text.secondary">סינונים לכלל</Typography>
                  <FormControlLabel control={<Checkbox checked={editTextFilterEnabled} onChange={(e) => setEditTextFilterEnabled(e.target.checked)} />} label="סינון מלל לאתר" />
                  <FormControlLabel control={<Checkbox checked={editImageFilterEnabled} onChange={(e) => setEditImageFilterEnabled(e.target.checked)} />} label="סינון תמונות לאתר" sx={{ display: 'block', mt: 0.5 }} />
                  <FormControlLabel control={<Checkbox checked={editFileFilterEnabled} onChange={(e) => setEditFileFilterEnabled(e.target.checked)} />} label="סינון קבצים לאתר" sx={{ display: 'block', mt: 0.5 }} />
                </Box>
              )}
              </>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ justifyContent: 'space-between', px: 2, pb: 1.5 }}>
          <Button onClick={() => setEditDialog(null)}>ביטול</Button>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            {editDialog?.request_type === 'file' && editDialog?.status === 'pending' && (
              <Button variant="contained" color="primary" onClick={() => { setApproveDialog(editDialog); setEditDialog(null); }}>
                אישור
              </Button>
            )}
            {editDialog?.request_type !== 'file' && (
              <>
            <Button variant="outlined" onClick={handleSaveEdit} disabled={saving || !!editUrlError}>{saving ? 'שומר...' : 'שמור'}</Button>
            {(editDialog?.status === 'pending' || editDialog?.status === 'rejected') && (
              <Button variant="contained" color="primary" onClick={saveEditThenOpenApprove} disabled={saving || !!editUrlError}>
                {editDialog?.status === 'pending' ? 'שמור ואשר' : 'שמור ואשר בקשה'}
              </Button>
            )}
            </>
            )}
            {(editDialog?.status === 'pending' || editDialog?.status === 'rejected') && (
              <>
                <IconButton
                  size="small"
                  onClick={(e) => setEditMoreAnchor(e.currentTarget)}
                  aria-label="פעולות נוספות"
                  sx={{ ml: 0.5 }}
                >
                  <MoreVertIcon />
                </IconButton>
                <Menu
                  anchorEl={editMoreAnchor}
                  open={!!editMoreAnchor}
                  onClose={() => setEditMoreAnchor(null)}
                  anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
                  transformOrigin={{ vertical: 'top', horizontal: 'left' }}
                >
                  {editDialog?.status === 'pending' && (
                    <MenuItem
                      onClick={() => {
                        setEditMoreAnchor(null);
                        if (editDialog) handleReject(editDialog);
                      }}
                    >
                      <ListItemIcon><CloseIcon fontSize="small" color="error" /></ListItemIcon>
                      <ListItemText primary="דחה" primaryTypographyProps={{ color: 'error' }} />
                    </MenuItem>
                  )}
                  <MenuItem
                    onClick={() => {
                      setEditMoreAnchor(null);
                      if (editDialog) handleDelete(editDialog);
                    }}
                  >
                    <ListItemIcon><DeleteIcon fontSize="small" color="error" /></ListItemIcon>
                    <ListItemText primary="מחק בקשה" primaryTypographyProps={{ color: 'error' }} />
                  </MenuItem>
                </Menu>
              </>
            )}
          </Box>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default AdminRequestsPage;
