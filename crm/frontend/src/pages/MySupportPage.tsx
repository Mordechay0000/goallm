/**
 * My Support – list inside a framed section (like reference).
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Container,
  Paper,
  Typography,
  Button,
  TablePagination,
} from '@mui/material';
import { Add as AddIcon, Notifications as NotificationsIcon, ChevronLeft as ChevronLeftIcon } from '@mui/icons-material';
import { supportApi } from '../api/support';
import type { SupportTicket } from '../api/support';

const formatDate = (ts: number) => {
  return new Date(ts * 1000).toLocaleString('he-IL', {
    dateStyle: 'short',
    timeStyle: 'short',
  });
};

const MySupportPage: React.FC = () => {
  const navigate = useNavigate();
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [error, setError] = useState('');

  const loadTickets = async () => {
    setLoading(true);
    try {
      const { tickets: list, total: t } = await supportApi.listTickets({
        page: page + 1,
        page_size: rowsPerPage,
        sort_order: 'desc',
        scope: 'mine',
      });
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
  }, [page, rowsPerPage]);

  const handleOpenTicket = (t: SupportTicket) => {
    navigate(`/support/${t.id}`);
  };

  return (
    <Container maxWidth="lg" sx={{ mt: { xs: 2, sm: 4 }, mb: 4, px: { xs: 2 } }} className="wrapper-content">
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 2, mb: 3 }}>
        <Box>
          <Typography variant="h5" component="h1" sx={{ fontWeight: 600, mb: 1 }}>
            הפניות שלי
          </Typography>
          <Typography variant="body2" color="text.secondary">
            צפייה בפניות ששלחת ותשובות מהתמיכה
          </Typography>
        </Box>
        <Button
          variant="contained"
          size="small"
          startIcon={<AddIcon />}
          onClick={() => navigate('/support/new')}
          sx={{ textTransform: 'none' }}
        >
          פנייה חדשה
        </Button>
      </Box>

      <Paper sx={{ p: 3 }}>
        {error && (
          <Box sx={{ py: 1, mb: 2, bgcolor: 'error.light', color: 'error.contrastText', px: 2, borderRadius: 1 }}>
            {error}
          </Box>
        )}

        <Typography variant="h6" sx={{ fontWeight: 600, mb: 1 }}>
          רשימת פניות
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {!loading ? `${total} פניות` : 'טוען...'}
        </Typography>

        {loading ? (
          <Box sx={{ py: 4, textAlign: 'center', color: 'text.secondary', fontSize: '0.875rem' }}>
            טוען...
          </Box>
        ) : tickets.length === 0 ? (
          <Box sx={{ py: 4, textAlign: 'center' }}>
            <Typography color="text.secondary" variant="body2" gutterBottom>
              אין פניות
            </Typography>
            <Button
              variant="outlined"
              size="small"
              startIcon={<AddIcon />}
              onClick={() => navigate('/support/new')}
              sx={{ mt: 1, textTransform: 'none' }}
            >
              צור פנייה חדשה
            </Button>
          </Box>
        ) : (
          <>
            <Box sx={{ width: '100%', bgcolor: 'background.paper', borderRadius: 1 }}>
              {tickets.map((t, idx) => (
                <Box
                  key={t.id}
                  onClick={() => handleOpenTicket(t)}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    py: 1.5,
                    borderBottom: idx < tickets.length - 1 ? '1px solid' : 'none',
                    borderColor: 'divider',
                    cursor: 'pointer',
                    transition: 'background-color 0.2s ease',
                    '&:hover': { bgcolor: 'action.selected' },
                    px: 1.5,
                  }}
                >
                  {(t.unread_replies_count ?? 0) > 0 && (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <NotificationsIcon sx={{ color: 'primary.main', fontSize: 20 }} titleAccess="תגובות שלא נקראו" />
                      <Typography variant="caption" color="primary.main" fontWeight={600}>
                        {t.unread_replies_count} הודעות לא נקראו
                      </Typography>
                    </Box>
                  )}
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Typography variant="body2" fontWeight={600} noWrap>
                      {t.subject}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" noWrap display="block">
                      {t.content_preview || '—'}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {formatDate(t.updated_at)}
                    </Typography>
                  </Box>
                  <Typography variant="caption" color="text.secondary" sx={{ flexShrink: 0 }}>
                    #{t.id}
                  </Typography>
                  <ChevronLeftIcon color="action" />
                </Box>
              ))}
            </Box>
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
              rowsPerPageOptions={[5, 10, 25]}
              labelRowsPerPage="שורות בעמוד"
              sx={{ mt: 1 }}
            />
          </>
        )}
      </Paper>
    </Container>
  );
};

export default MySupportPage;
