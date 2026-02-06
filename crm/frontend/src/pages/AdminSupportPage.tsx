/**
 * Admin: all support tickets.
 * Table with subject, start of content, user; reply icon when has replies.
 * Click opens conversation on separate page.
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
} from '@mui/material';
import { Notifications as NotificationsIcon, Search as SearchIcon } from '@mui/icons-material';
import { supportApi } from '../api/support';
import type { SupportTicket } from '../api/support';

const formatDate = (ts: number) => {
  return new Date(ts * 1000).toLocaleString('he-IL', {
    dateStyle: 'short',
    timeStyle: 'short',
  });
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
  const [error, setError] = useState('');

  const loadTickets = async () => {
    setLoading(true);
    try {
      const params: Record<string, string | number> = {
        page: page + 1,
        page_size: rowsPerPage,
        sort_order: sortOrder,
      };
      if (search.trim()) params.search = search.trim();
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

  useEffect(() => {
    loadTickets();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- loadTickets reads page, rowsPerPage, sortOrder, search
  }, [page, rowsPerPage, sortOrder, search]);

  const handleOpenTicket = (t: SupportTicket) => {
    navigate(`/admin/support/${t.id}`);
  };

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
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

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
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
                <TableCell sx={{ width: 80 }} />
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
              {tickets.map((t) => (
                <TableRow
                  key={t.id}
                  hover
                  sx={{ cursor: 'pointer', '&:hover': { bgcolor: 'action.selected' } }}
                  onClick={() => handleOpenTicket(t)}
                >
                  <TableCell sx={{ width: 80 }}>
                    {(t.unread_replies_count ?? 0) > 0 ? (
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <NotificationsIcon sx={{ color: 'primary.main', fontSize: 18 }} titleAccess="הודעות שלא נקראו" />
                        <Typography component="span" variant="caption" fontWeight={600} color="primary.main">
                          {t.unread_replies_count}
                        </Typography>
                      </Box>
                    ) : null}
                  </TableCell>
                  <TableCell sx={{ whiteSpace: 'nowrap' }}>
                    {formatDate(t.updated_at)}
                  </TableCell>
                  <TableCell sx={{ fontWeight: 500 }}>{t.subject}</TableCell>
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
              ))}
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
      </Paper>
    </Container>
  );
};

export default AdminSupportPage;
