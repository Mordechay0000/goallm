/**
 * Admin: list users and select one to manage (profiles/rules).
 * Cannot manage self (current user). Sort by column header, pagination.
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Container,
  Paper,
  Typography,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  TableSortLabel,
  TablePagination,
  TextField,
  InputAdornment,
} from '@mui/material';
import { Person as PersonIcon, Delete as DeleteIcon, Search as SearchIcon } from '@mui/icons-material';
import { adminApi } from '../api/admin';
import type { AdminUser } from '../api/admin';
import { useManagedUserStore } from '../store/managedUserStore';
import { useAuthStore } from '../store/authStore';
import { PAGE_DESCRIPTIONS, PLACEHOLDERS } from '../brand';

type Order = 'asc' | 'desc';
type SortBy = 'id' | 'phone' | 'first_name' | 'email' | 'is_admin' | 'created_at';

const ROWS_PER_PAGE_OPTIONS = [10, 25, 50, 100];

const AdminUsersPage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const { setManagedUser } = useManagedUserStore();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [deleteConfirm, setDeleteConfirm] = useState<AdminUser | null>(null);
  const [order, setOrder] = useState<Order>('asc');
  const [orderBy, setOrderBy] = useState<SortBy>('id');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [search, setSearch] = useState('');

  const loadUsers = async () => {
    setLoading(true);
    try {
      const { users: list, total: t } = await adminApi.listUsers({
        sort_by: orderBy,
        sort_order: order,
        page: page + 1,
        page_size: rowsPerPage,
        search: search.trim() || undefined,
      });
      setUsers(list);
      setTotal(t);
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string } } };
      alert(ax?.response?.data?.detail || 'שגיאה בטעינת משתמשים');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- loadUsers reads order, orderBy, page, rowsPerPage, search
  }, [order, orderBy, page, rowsPerPage, search]);

  const handleSort = (col: SortBy) => {
    const isAsc = orderBy === col && order === 'asc';
    setOrder(isAsc ? 'desc' : 'asc');
    setOrderBy(col);
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

  const handleManage = (u: AdminUser) => {
    setManagedUser(u.id, u.phone || '');
    navigate('/profiles');
  };

  const handleDeleteClick = (u: AdminUser) => setDeleteConfirm(u);

  const handleDeleteConfirm = async () => {
    if (!deleteConfirm) return;
    try {
      await adminApi.deleteUser(deleteConfirm.id);
      setDeleteConfirm(null);
      await loadUsers();
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string } } };
      alert(ax?.response?.data?.detail || 'שגיאה במחיקת משתמש');
    }
  };

  const isCurrentUser = (u: AdminUser) => user?.id === u.id;

  if (loading && users.length === 0) {
    return <Container sx={{ mt: 4, mb: 4 }}>טוען...</Container>;
  }

  return (
    <Container maxWidth="lg" sx={{ mb: 4 }} className="page-section container-content">
      <Box className="page-title-section" sx={{ mb: 3 }}>
        <Typography variant="h5" component="h1" sx={{ fontWeight: 600, mb: 1 }}>
          ניהול משתמשים
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {PAGE_DESCRIPTIONS.adminUsers}
        </Typography>
      </Box>
      <Paper className="paper-table">
        <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 2, px: 2, pt: 2, pb: 1.5, borderBottom: '1px solid', borderColor: 'divider' }}>
          <TextField
            size="small"
            placeholder={PLACEHOLDERS.search}
            value={search}
            onChange={handleSearchChange}
            sx={{ minWidth: 260 }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" color="action" />
                </InputAdornment>
              ),
            }}
          />
        </Box>
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell sortDirection={orderBy === 'phone' ? order : false}>
                  <TableSortLabel
                    active={orderBy === 'phone'}
                    direction={orderBy === 'phone' ? order : 'asc'}
                    onClick={() => handleSort('phone')}
                  >
                    טלפון
                  </TableSortLabel>
                </TableCell>
                <TableCell sortDirection={orderBy === 'first_name' ? order : false}>
                  <TableSortLabel
                    active={orderBy === 'first_name'}
                    direction={orderBy === 'first_name' ? order : 'asc'}
                    onClick={() => handleSort('first_name')}
                  >
                    שם
                  </TableSortLabel>
                </TableCell>
                <TableCell sortDirection={orderBy === 'email' ? order : false}>
                  <TableSortLabel
                    active={orderBy === 'email'}
                    direction={orderBy === 'email' ? order : 'asc'}
                    onClick={() => handleSort('email')}
                  >
                    אימייל
                  </TableSortLabel>
                </TableCell>
                <TableCell sortDirection={orderBy === 'is_admin' ? order : false}>
                  <TableSortLabel
                    active={orderBy === 'is_admin'}
                    direction={orderBy === 'is_admin' ? order : 'asc'}
                    onClick={() => handleSort('is_admin')}
                  >
                    מנהל
                  </TableSortLabel>
                </TableCell>
                <TableCell align="left">פעולה</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {users.map((u) => (
                <TableRow key={u.id}>
                  <TableCell>{u.phone}</TableCell>
                  <TableCell>{[u.first_name, u.last_name].filter(Boolean).join(' ') || '—'}</TableCell>
                  <TableCell>{u.email || '—'}</TableCell>
                  <TableCell>{u.is_admin ? <Chip label="מנהל" size="small" color="primary" /> : '—'}</TableCell>
                  <TableCell align="left">
                    {isCurrentUser(u) ? (
                      <Chip label="אתה" size="small" color="default" variant="outlined" />
                    ) : (
                      <>
                        <Button
                          variant="outlined"
                          size="small"
                          startIcon={<PersonIcon />}
                          onClick={() => handleManage(u)}
                          sx={{ mr: 0.5 }}
                        >
                          נהל
                        </Button>
                        <IconButton
                          size="small"
                          color="error"
                          onClick={() => handleDeleteClick(u)}
                          title="מחק משתמש"
                        >
                          <DeleteIcon />
                        </IconButton>
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

      <Dialog open={!!deleteConfirm} onClose={() => setDeleteConfirm(null)}>
        <DialogTitle>מחיקת משתמש</DialogTitle>
        <DialogContent>
          <DialogContentText>
            האם אתה בטוח שברצונך למחוק את המשתמש{' '}
            {deleteConfirm ? [deleteConfirm.first_name, deleteConfirm.last_name].filter(Boolean).join(' ') || deleteConfirm.phone : ''}?
            כל הפרופילים, הכללים והנתונים שלו יימחקו לצמיתות.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteConfirm(null)}>ביטול</Button>
          <Button color="error" variant="contained" onClick={handleDeleteConfirm}>
            מחק
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default AdminUsersPage;
