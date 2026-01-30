/**
 * Admin: list all rule requests with filters, sort, edit, approve/reject/delete.
 * Row click: approved → rules page; pending/rejected → edit dialog.
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
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
import { profilesApi } from '../api/profiles';
import { adminApi } from '../api/admin';
import type { RuleRequest, RuleRequestUpdate } from '../api/ruleRequests';
import type { Profile } from '../api/profiles';

const STATUS_LABELS: Record<string, string> = {
  pending: 'ממתין',
  approved: 'אושר',
  rejected: 'נדחה',
};

const TYPE_LABELS: Record<string, string> = {
  open: 'בקשה לפתיחה',
  change: 'בקשה לשינוי',
};

interface ProfileOption extends Profile {
  user_phone?: string;
}

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
  const [profiles, setProfiles] = useState<ProfileOption[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<number | ''>('');
  const [editDialog, setEditDialog] = useState<RuleRequest | null>(null);
  const [editUrl, setEditUrl] = useState('');
  const [editAction, setEditAction] = useState<'allow' | 'block'>('block');
  const [editType, setEditType] = useState<string>('*');
  const [editIncludeSubdomains, setEditIncludeSubdomains] = useState(false);
  const [editTags, setEditTags] = useState<string[]>([]);
  const [editTagInput, setEditTagInput] = useState('');
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

  const loadProfilesForApprove = (req: RuleRequest) => {
    if (req.is_from_blocked_page) {
      adminApi.listAllProfiles().then((list) => {
        setProfiles(list as ProfileOption[]);
        setSelectedProfileId('');
      }).catch(() => setProfiles([]));
    } else {
      profilesApi.list(req.user_id).then((list) => {
        setProfiles(list as ProfileOption[]);
        if (list.length === 1) setSelectedProfileId(list[0].id);
        else setSelectedProfileId('');
      }).catch(() => setProfiles([]));
    }
  };

  const handleApproveClick = (req: RuleRequest) => {
    setApproveDialog(req);
    setSelectedProfileId('');
    loadProfilesForApprove(req);
  };

  const handleApproveConfirm = async () => {
    if (!approveDialog || selectedProfileId === '') {
      alert('נא לבחור פרופיל');
      return;
    }
    try {
      await ruleRequestsApi.approve(approveDialog.id, selectedProfileId as number);
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
    setEditUrl(req.url || (req.domain_pattern || '') + (req.path_pattern || '') || '');
    setEditAction((req.action as 'allow' | 'block') || 'block');
    setEditType(req.type || '*');
    setEditIncludeSubdomains(!!req.include_subdomains);
    setEditTags(normalizeTags(req.tags));
    setEditTagInput('');
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
    if (req.status === 'approved' && req.approved_profile_id) {
      navigate(`/profiles/${req.approved_profile_id}/rules`);
      return;
    }
    if (req.status === 'pending' || req.status === 'rejected') {
      openEditDialog(req);
    }
  };

  const addEditTag = () => {
    const v = editTagInput.trim();
    if (v && !editTags.includes(v)) {
      setEditTags((prev) => [...prev, v]);
      setEditTagInput('');
    }
  };

  const removeEditTag = (index: number) => {
    setEditTags((prev) => prev.filter((_, i) => i !== index));
  };

  const handleEditTagKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      addEditTag();
    } else if (e.key === 'Backspace' && !editTagInput && editTags.length > 0) {
      setEditTags((prev) => prev.slice(0, -1));
    }
  };

  const saveEditThenOpenApprove = async () => {
    if (!editDialog) return;
    if (!editUrl.trim()) {
      alert('נא להזין כתובת');
      return;
    }
    setSaving(true);
    try {
      const data: RuleRequestUpdate = {
        url: editUrl.trim(),
        action: editAction,
        type: editType as '*' | 'image' | 'video',
        include_subdomains: editIncludeSubdomains,
        tags: editTags.length > 0 ? editTags : undefined,
      };
      await ruleRequestsApi.update(editDialog.id, data);
      const reqToApprove = { ...editDialog, ...data };
      setEditDialog(null);
      await loadRequests();
      setApproveDialog(reqToApprove);
      loadProfilesForApprove(reqToApprove);
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string } } };
      alert(ax?.response?.data?.detail || 'שגיאה בשמירה');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveEdit = async () => {
    if (!editDialog) return;
    if (!editUrl.trim()) {
      alert('נא להזין כתובת');
      return;
    }
    setSaving(true);
    try {
      const data: RuleRequestUpdate = {
        url: editUrl.trim(),
        action: editAction,
        type: editType as '*' | 'image' | 'video',
        include_subdomains: editIncludeSubdomains,
        tags: editTags.length > 0 ? editTags : undefined,
      };
      await ruleRequestsApi.update(editDialog.id, data);
      setEditDialog(null);
      await loadRequests();
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
    <Container maxWidth="xl" sx={{ mt: 4 }}>
      <Typography variant="h4" gutterBottom>
        בקשות משתמשים
      </Typography>

      <Paper sx={{ p: 2, mb: 2 }}>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center' }}>
          <TextField
            size="small"
            placeholder="חיפוש (כתובת, דומיין)..."
            value={search}
            onChange={handleSearchChange}
            sx={{ minWidth: 220 }}
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
        <Paper>
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
                  sx={{ cursor: r.status === 'approved' && r.approved_profile_id ? 'pointer' : (r.status === 'pending' || r.status === 'rejected') ? 'pointer' : 'default' }}
                  onClick={() => handleRowClick(r)}
                >
                  <TableCell>{formatDate(r.created_at)}</TableCell>
                  <TableCell>{TYPE_LABELS[r.request_type] || r.request_type}</TableCell>
                  <TableCell>
                    <Chip
                      label={STATUS_LABELS[r.status] || r.status}
                      size="small"
                      color={r.status === 'approved' ? 'success' : r.status === 'rejected' ? 'error' : 'default'}
                    />
                  </TableCell>
                  <TableCell>{r.user_phone ?? (r.user_id ? '—' : 'מעמוד חסום')}</TableCell>
                  <TableCell>{r.url || (r.domain_pattern || '') + (r.path_pattern || '') || '—'}</TableCell>
                  <TableCell>{r.action || '—'} / {r.type || '*'}</TableCell>
                  <TableCell align="left" onClick={(e) => e.stopPropagation()}>
                    {r.status === 'pending' && (
                      <>
                        <Button size="small" color="primary" startIcon={<CheckIcon />} onClick={() => handleApproveClick(r)}>אשר</Button>
                        <Button size="small" color="error" startIcon={<CloseIcon />} onClick={() => handleReject(r)}>דחה</Button>
                        <Button size="small" startIcon={<EditIcon />} onClick={() => openEditDialog(r)}>עריכה</Button>
                        <IconButton size="small" onClick={(e) => handleDelete(r, e)} title="מחק"><DeleteIcon /></IconButton>
                      </>
                    )}
                    {r.status === 'rejected' && (
                      <>
                        <Button size="small" color="primary" startIcon={<CheckIcon />} onClick={() => handleApproveClick(r)}>אשר</Button>
                        <Button size="small" startIcon={<EditIcon />} onClick={() => openEditDialog(r)}>עריכה</Button>
                        <IconButton size="small" onClick={(e) => handleDelete(r, e)} title="מחק"><DeleteIcon /></IconButton>
                      </>
                    )}
                    {r.status === 'approved' && (
                      <>
                        <Button size="small" startIcon={<EditIcon />} onClick={() => navigate(`/profiles/${r.approved_profile_id}/rules`)}>לכלל</Button>
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
      )}

      {/* Approve: select profile */}
      <Dialog open={!!approveDialog} onClose={() => setApproveDialog(null)}>
        <DialogTitle>אישור בקשה – בחר פרופיל</DialogTitle>
        <DialogContent>
          <FormControl fullWidth sx={{ mt: 1 }}>
            <InputLabel>פרופיל</InputLabel>
            <Select
              value={selectedProfileId}
              label="פרופיל"
              onChange={(e) => setSelectedProfileId(e.target.value as number)}
            >
              <MenuItem value="">בחר פרופיל</MenuItem>
              {profiles.map((p) => (
                <MenuItem key={p.id} value={p.id}>
                  {p.name}{(p as ProfileOption).user_phone ? ` (${(p as ProfileOption).user_phone})` : ''}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setApproveDialog(null)}>ביטול</Button>
          <Button variant="contained" onClick={handleApproveConfirm} disabled={selectedProfileId === ''}>אישור</Button>
        </DialogActions>
      </Dialog>

      {/* Edit dialog */}
      <Dialog open={!!editDialog} onClose={() => setEditDialog(null)} maxWidth="sm" fullWidth>
        <DialogTitle>{editDialog?.status === 'rejected' ? 'עריכת בקשה (נדחה)' : 'עריכת בקשה'}</DialogTitle>
        <DialogContent>
          {editDialog && (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
              <TextField
                fullWidth
                label="כתובת מלאה (לא לעריכה)"
                value={editDialog.request_url || editDialog.url || (editDialog.domain_pattern || '') + (editDialog.path_pattern || '') || '—'}
                InputProps={{ readOnly: true }}
                sx={{ '& .MuiInputBase-input': { color: 'text.secondary', bgcolor: 'action.hover' } }}
                size="small"
              />
              <TextField fullWidth label="כתובת אתר" value={editUrl} onChange={(e) => setEditUrl(e.target.value)} placeholder="example.com" />
              <FormControl fullWidth>
                <InputLabel>פעולה</InputLabel>
                <Select value={editAction} label="פעולה" onChange={(e) => setEditAction(e.target.value as 'allow' | 'block')}>
                  <MenuItem value="allow">אפשר</MenuItem>
                  <MenuItem value="block">חסום</MenuItem>
                </Select>
              </FormControl>
              <FormControl fullWidth>
                <InputLabel>סוג</InputLabel>
                <Select value={editType} label="סוג" onChange={(e) => setEditType(e.target.value)}>
                  <MenuItem value="*">הכל</MenuItem>
                  <MenuItem value="image">תמונה</MenuItem>
                  <MenuItem value="video">וידאו</MenuItem>
                </Select>
              </FormControl>
              <FormControlLabel control={<Checkbox checked={editIncludeSubdomains} onChange={(e) => setEditIncludeSubdomains(e.target.checked)} />} label="כולל סאב-דומיינים" />
              <Box>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>תגיות</Typography>
                <Box
                  sx={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: 0.75,
                    alignItems: 'center',
                    minHeight: 42,
                    px: 1.25,
                    py: 0.75,
                    borderRadius: 1,
                    border: '1px solid',
                    borderColor: 'divider',
                    bgcolor: 'action.hover',
                    '&:focus-within': { borderColor: 'primary.main', bgcolor: 'background.paper' },
                  }}
                >
                  {editTags.map((t, i) => (
                    <Chip key={`${i}-${t}`} label={t} size="small" onDelete={() => removeEditTag(i)} />
                  ))}
                  <TextField
                    size="small"
                    placeholder="הקלד תגית והקש פסיק או Enter"
                    value={editTagInput}
                    onChange={(e) => setEditTagInput(e.target.value)}
                    onKeyDown={handleEditTagKeyDown}
                    variant="standard"
                    InputProps={{ disableUnderline: true }}
                    sx={{ minWidth: 180, flex: 1, '& .MuiInput-root': { fontSize: '0.875rem' } }}
                  />
                  <Button size="small" variant="outlined" onClick={addEditTag} sx={{ flexShrink: 0 }}>הוסף</Button>
                </Box>
              </Box>
            </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ justifyContent: 'space-between', px: 2, pb: 1.5 }}>
          <Button onClick={() => setEditDialog(null)}>ביטול</Button>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <Button variant="outlined" onClick={handleSaveEdit} disabled={saving}>{saving ? 'שומר...' : 'שמור'}</Button>
            {(editDialog?.status === 'pending' || editDialog?.status === 'rejected') && (
              <Button variant="contained" color="primary" onClick={saveEditThenOpenApprove} disabled={saving}>
                {editDialog?.status === 'pending' ? 'שמור ואשר' : 'שמור ואשר בקשה'}
              </Button>
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
