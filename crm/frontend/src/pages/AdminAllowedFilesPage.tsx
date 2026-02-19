/**
 * Admin: manage global allowed file downloads list. Admin only.
 * Similar to global rules page but for file URLs that were approved for download.
 */
import React, { useEffect, useState } from 'react';
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
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  TablePagination,
  InputAdornment,
} from '@mui/material';
import { Add as AddIcon, Delete as DeleteIcon, Search as SearchIcon } from '@mui/icons-material';
import { adminApi, type AllowedFileItem } from '../api/admin';
import { PAGE_DESCRIPTIONS, PLACEHOLDERS } from '../brand';

const ROWS_PER_PAGE_OPTIONS = [10, 25, 50, 100];

function formatDate(ts: number): string {
  const d = new Date(ts * 1000);
  return d.toLocaleDateString('he-IL') + ' ' + d.toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' });
}

const AdminAllowedFilesPage: React.FC = () => {
  const [items, setItems] = useState<AllowedFileItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [newUrl, setNewUrl] = useState('');
  const [newUrlError, setNewUrlError] = useState('');
  const [saving, setSaving] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<AllowedFileItem | null>(null);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);

  const loadItems = async () => {
    setLoading(true);
    try {
      const list = await adminApi.listAllowedFileDownloads();
      setItems(list);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadItems();
  }, []);

  const filtered = search.trim()
    ? items.filter((i) => i.url.toLowerCase().includes(search.trim().toLowerCase()))
    : items;
  const paginated = filtered.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage);

  const openAdd = () => {
    setNewUrl('');
    setNewUrlError('');
    setDialogOpen(true);
  };

  const handleAdd = async () => {
    const url = newUrl.trim();
    if (!url) {
      setNewUrlError('נא להזין כתובת קובץ');
      return;
    }
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      setNewUrlError('הכתובת חייבת להתחיל ב־http:// או https://');
      return;
    }
    setSaving(true);
    try {
      await adminApi.addAllowedFileDownload(url);
      setDialogOpen(false);
      await loadItems();
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string } } };
      setNewUrlError(ax?.response?.data?.detail || 'שגיאה בהוספה');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (item: AllowedFileItem) => {
    try {
      await adminApi.removeAllowedFileDownload(item.url);
      setDeleteConfirm(null);
      await loadItems();
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string } } };
      alert(ax?.response?.data?.detail || 'שגיאה במחיקה');
    }
  };

  return (
    <Container maxWidth="lg" sx={{ mb: 4, px: { xs: 0 } }} className="page-section container-content">
      <Box className="page-title-section" sx={{ mb: 3 }}>
        <Typography variant="h5" component="h1" sx={{ fontWeight: 600, mb: 1 }}>
          רשימת הקבצים הגלובלית
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {PAGE_DESCRIPTIONS.adminGlobalFiles}
        </Typography>
      </Box>

      <Paper className="paper-table">
        <Box className="card-header-accent spectrum-alt1" sx={{ px: 2, pt: 2, pb: 1 }}>
          <Typography className="section-title">קבצים מאושרים</Typography>
        </Box>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 1, px: 2, pt: 1.5, pb: 1.5, borderBottom: '1px solid', borderColor: 'divider' }}>
          <TextField
            size="small"
            fullWidth
            placeholder={PLACEHOLDERS.search}
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(0); }}
            sx={{ minWidth: { xs: '100%', sm: 260 } }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" color="action" />
                </InputAdornment>
              ),
            }}
          />
          <Button variant="contained" startIcon={<AddIcon sx={{ display: { xs: 'none', sm: 'inline-flex' } }} />} onClick={openAdd} fullWidth sx={{ minWidth: { sm: 'auto' } }}>
            הוסף כתובת קובץ
          </Button>
        </Box>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell align="right">כתובת הקובץ</TableCell>
                <TableCell align="left">תאריך הוספה</TableCell>
                <TableCell align="center" sx={{ width: 72 }}>פעולות</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                <TableRow><TableCell colSpan={3}>טוען...</TableCell></TableRow>
              ) : filtered.length === 0 ? (
                <TableRow><TableCell colSpan={3}>{items.length === 0 ? 'אין קבצים ברשימה' : 'אין תוצאות לחיפוש'}</TableCell></TableRow>
              ) : (
                paginated.map((item) => (
                  <TableRow key={item.url} hover sx={{ '&:hover': { bgcolor: 'action.selected' } }}>
                    <TableCell
                      align="right"
                      sx={{
                        maxWidth: 480,
                        overflowX: 'auto',
                        whiteSpace: 'nowrap',
                        scrollbarWidth: 'thin',
                        '&::-webkit-scrollbar': { height: 8 },
                      }}
                      title={item.url}
                    >
                      {item.url}
                    </TableCell>
                    <TableCell align="left" sx={{ whiteSpace: 'nowrap' }}>{formatDate(item.created_at)}</TableCell>
                    <TableCell align="center">
                      <IconButton size="small" color="error" onClick={() => setDeleteConfirm(item)} title="הסר"><DeleteIcon /></IconButton>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
        {filtered.length > 0 && (
          <TablePagination
            component="div"
            count={filtered.length}
            page={page}
            onPageChange={(_, p) => setPage(p)}
            rowsPerPage={rowsPerPage}
            onRowsPerPageChange={(e) => { setRowsPerPage(parseInt(e.target.value, 10)); setPage(0); }}
            rowsPerPageOptions={ROWS_PER_PAGE_OPTIONS}
            labelRowsPerPage="שורות בעמוד:"
            labelDisplayedRows={({ from, to, count }) => `${from}–${to} מתוך ${count}`}
          />
        )}
      </Paper>

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>הוספת כתובת קובץ מאושר</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            label="כתובת הקובץ (URL)"
            value={newUrl}
            onChange={(e) => {
              setNewUrl(e.target.value);
              setNewUrlError('');
            }}
            placeholder="https://example.com/files/document.pdf"
            error={!!newUrlError}
            helperText={newUrlError}
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>ביטול</Button>
          <Button variant="contained" onClick={handleAdd} disabled={saving}>{saving ? 'מוסיף...' : 'הוסף'}</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={!!deleteConfirm} onClose={() => setDeleteConfirm(null)}>
        <DialogTitle>הסרת קובץ מהרשימה</DialogTitle>
        <DialogContent>
          <Typography variant="body2">להסיר את הכתובת מהרשימה? לאחר ההסרה, הורדות מכתובת זו יישלחו שוב לבדיקה.</Typography>
          {deleteConfirm && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1, wordBreak: 'break-all' }}>{deleteConfirm.url}</Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteConfirm(null)}>ביטול</Button>
          <Button color="error" variant="contained" onClick={() => deleteConfirm && handleDelete(deleteConfirm)}>הסר</Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default AdminAllowedFilesPage;
