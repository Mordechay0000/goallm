/**
 * Admin: all support tickets. Filters (read/unread, user), select rows, bulk delete.
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Typography,
  Box,
  Container,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TableSortLabel,
  TablePagination,
  TextField,
  InputAdornment,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Checkbox,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import { Search as SearchIcon, Delete as DeleteIcon } from '@mui/icons-material';
import { supportApi } from '../api/support';
import type { SupportTicket } from '../api/support';

type ReadFilter = 'all' | 'unread' | 'read';

interface TicketUser {
  id: number;
  first_name?: string;
  last_name?: string;
  phone?: string;
}

const formatDate = (ts: number) => {
  return new Date(ts * 1000).toLocaleString('he-IL', {
    dateStyle: 'short',
    timeStyle: 'short',
  });
};

const userLabel = (u: TicketUser) => {
  const name = [u.first_name, u.last_name].filter(Boolean).join(' ');
  return name ? `${name}${u.phone ? ` (${u.phone})` : ''}` : u.phone || `#${u.id}`;
};

const AdminSupportPage: React.FC = () => {
  const navigate = useNavigate();
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [search, setSearch] = useState('');
  const [readFilter, setReadFilter] = useState<ReadFilter>('all');
  const [userIdFilter, setUserIdFilter] = useState<number | ''>('');
  const [ticketUsers, setTicketUsers] = useState<TicketUser[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState('');

  const loadTickets = async () => {
    setLoading(true);
    setError('');
    try {
      const params: Record<string, string | number> = {
        page: page + 1,
        page_size: rowsPerPage,
        sort_order: sortOrder,
      };
      if (search.trim()) params.search = search.trim();
      if (readFilter !== 'all') params.read_filter = readFilter;
      if (userIdFilter !== '') params.user_id = userIdFilter as number;
      const { tickets: list, total: t } = await supportApi.listTickets(params);
      setTickets(list);
      setTotal(t);
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string } } };
      setError(ax?.response?.data?.detail || 'שגיאה בטעינת הפניות');
    } finally {
      setLoading(false);
    }
  };

  const loadTicketUsers = async () => {
    try {
      const { users } = await supportApi.listTicketUsers();
      setTicketUsers(users || []);
    } catch {
      setTicketUsers([]);
    }
  };

  useEffect(() => {
    loadTickets();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- loadTickets reads page, rowsPerPage, sortOrder, search, readFilter, userIdFilter
  }, [page, rowsPerPage, sortOrder, search, readFilter, userIdFilter]);

  useEffect(() => {
    loadTicketUsers();
  }, []);

  const handleOpenTicket = (t: SupportTicket) => {
    navigate(`/admin/support/${t.id}`);
  };

  const toggleSelect = (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (selectedIds.size === tickets.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(tickets.map((t) => t.id)));
    }
  };

  const handleBulkDelete = () => {
    setDeleteDialogOpen(true);
  };

  const confirmBulkDelete = async () => {
    if (selectedIds.size === 0) return;
    setDeleting(true);
    try {
      const ids = Array.from(selectedIds);
      const { deleted } = await supportApi.bulkDeleteTickets(ids);
      setSelectedIds(new Set());
      setDeleteDialogOpen(false);
      if (deleted > 0) {
        await loadTickets();
        setPage(0);
      }
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string } } };
      setError(ax?.response?.data?.detail || 'שגיאה במחיקה');
    } finally {
      setDeleting(false);
    }
  };

  const allSelected = tickets.length > 0 && selectedIds.size === tickets.length;
  const someSelected = selectedIds.size > 0;

  return (
    <Container maxWidth="lg" sx={{ mt: { xs: 2, sm: 4 }, mb: 4, px: { xs: 2 } }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" component="h1" sx={{ fontWeight: 600, mb: 1 }}>
          פניות משתמשים (אדמין)
        </Typography>
      </Box>

      <Paper sx={{ p: 3 }}>
        {error && (
          <Box sx={{ py: 1, mb: 2, bgcolor: 'error.light', color: 'error.contrastText', px: 2, borderRadius: 1 }}>
            {error}
          </Box>
        )}

        <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 2, mb: 2 }}>
          <TextField
            size="small"
            placeholder="חיפוש נושא, תוכן, משתמש"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(0); }}
            sx={{ minWidth: 220 }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
            }}
          />
          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel>סטטוס קריאה</InputLabel>
            <Select
              value={readFilter}
              label="סטטוס קריאה"
              onChange={(e) => { setReadFilter(e.target.value as ReadFilter); setPage(0); }}
            >
              <MenuItem value="all">הכל</MenuItem>
              <MenuItem value="unread">שלא נקראו</MenuItem>
              <MenuItem value="read">נקראו</MenuItem>
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 180 }}>
            <InputLabel>משתמש</InputLabel>
            <Select
              value={userIdFilter === '' ? '' : String(userIdFilter)}
              label="משתמש"
              onChange={(e) => { setUserIdFilter(e.target.value === '' ? '' : Number(e.target.value)); setPage(0); }}
            >
              <MenuItem value="">כל המשתמשים</MenuItem>
              {ticketUsers.map((u) => (
                <MenuItem key={u.id} value={String(u.id)}>{userLabel(u)}</MenuItem>
              ))}
            </Select>
          </FormControl>
          {someSelected && (
            <Button
              variant="outlined"
              color="error"
              size="small"
              startIcon={<DeleteIcon />}
              onClick={handleBulkDelete}
            >
              מחק נבחרים ({selectedIds.size})
            </Button>
          )}
        </Box>

      {loading ? (
        <Box sx={{ py: 4, textAlign: 'center' }}>טוען...</Box>
      ) : tickets.length === 0 ? (
        <Box sx={{ py: 4, textAlign: 'center', color: 'text.secondary' }}>
          אין פניות.
        </Box>
      ) : (
        <>
          <Table size="small" sx={{ width: '100%' }}>
            <TableHead>
              <TableRow>
                <TableCell padding="checkbox" sx={{ width: 48 }}>
                  <Checkbox
                    indeterminate={someSelected && !allSelected}
                    checked={allSelected}
                    onChange={() => {}}
                    onClick={toggleSelectAll}
                    size="small"
                    aria-label="בחר הכל"
                  />
                </TableCell>
                <TableCell sortDirection={sortOrder}>
                  <TableSortLabel active direction={sortOrder} onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}>
                    תאריך
                  </TableSortLabel>
                </TableCell>
                <TableCell>נושא</TableCell>
                <TableCell>תחילת תוכן</TableCell>
                <TableCell>משתמש</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {tickets.map((t) => {
                const hasUnread = (t.unread_user_replies_for_admin ?? 0) > 0;
                const checked = selectedIds.has(t.id);
                return (
                <TableRow
                  key={t.id}
                  hover
                  selected={checked}
                  sx={{
                    cursor: 'pointer',
                    position: 'relative',
                    // 1) Indicator ברוחב 4px בצד ימין, בגובה חלקי (לא מחובר למעלה/למטה ולא יוצר פס רציף)
                    ...(hasUnread && {
                      '&::before': {
                        content: '""',
                        position: 'absolute',
                        right: 0,
                        top: '16%',
                        height: '68%', // בערך 2/3 מהשורה
                        width: '4px',
                        borderRadius: '8px 0 0 8px',
                        backgroundColor: 'primary.main',
                      },
                    }),
                    // 3) צל פנימי עדין – עומק קל, שומר על ה-striping
                    boxShadow: hasUnread ? 'inset 0 0 0 1px rgba(15, 23, 42, 0.10)' : undefined,
                    // 4) רקע primary שקוף מאוד – עומק בלי לחסום את הזברה
                    bgcolor: hasUnread ? 'rgba(25, 118, 210, 0.045)' : undefined,
                    '&:hover': { bgcolor: 'action.selected' },
                  }}
                  onClick={() => handleOpenTicket(t)}
                  title={hasUnread ? 'יש תגובות משתמש שלא נקראו' : undefined}
                >
                  <TableCell padding="checkbox" onClick={(e) => toggleSelect(t.id, e)}>
                    <Checkbox checked={checked} size="small" />
                  </TableCell>
                  <TableCell sx={{ whiteSpace: 'nowrap' }}>
                    {formatDate(t.updated_at)}
                  </TableCell>
                  <TableCell sx={{ fontWeight: hasUnread ? 600 : undefined }}>
                    {t.subject}
                  </TableCell>
                  <TableCell sx={{ maxWidth: 320 }} title={t.content_preview}>
                    <Typography variant="body2" noWrap sx={{ maxWidth: 320 }}>
                      {t.content_preview || '—'}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    {t.user_first_name ? `${t.user_first_name}` : '—'}
                    {t.user_phone && (
                      <Typography variant="caption" display="block" color="text.secondary">
                        {t.user_phone}
                      </Typography>
                    )}
                  </TableCell>
                </TableRow>
              );
              })}
            </TableBody>
          </Table>
          <TablePagination
            component="div"
            count={total}
            page={page}
            onPageChange={(_, p) => setPage(p)}
            rowsPerPage={rowsPerPage}
            onRowsPerPageChange={(e) => {
              setRowsPerPage(parseInt(e.target.value, 10));
              setPage(0);
            }}
            rowsPerPageOptions={[10, 25, 50]}
            labelRowsPerPage="שורות בעמוד"
          />
        </>
      )}

      <Dialog open={deleteDialogOpen} onClose={() => !deleting && setDeleteDialogOpen(false)}>
        <DialogTitle>מחיקת פניות</DialogTitle>
        <DialogContent>
          <Typography>
            למחוק {selectedIds.size} פניות? לא ניתן לשחזר.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)} disabled={deleting}>ביטול</Button>
          <Button variant="contained" color="error" onClick={confirmBulkDelete} disabled={deleting}>
            {deleting ? 'מוחק...' : 'מחק'}
          </Button>
        </DialogActions>
      </Dialog>
      </Paper>
    </Container>
  );
};

export default AdminSupportPage;
