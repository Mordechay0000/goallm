/**
 * חיבורים (שיוכי IP) – הצגת כל המכשירים המשויכים לחשבון ואפשרות לבטל שיוך.
 */
import React, { useEffect, useState } from 'react';
import {
  Box,
  Container,
  Paper,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  IconButton,
  Alert,
} from '@mui/material';
import { Delete as DeleteIcon } from '@mui/icons-material';
import { bindingsApi, type IpBinding } from '../api/bindings';

type SortBy = 'ip' | 'created_at' | 'last_used_at';
type SortOrder = 'asc' | 'desc';

const ConnectionsPage: React.FC = () => {
  const [bindings, setBindings] = useState<IpBinding[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const [orderBy, setOrderBy] = useState<SortBy>('last_used_at');
  const [order, setOrder] = useState<SortOrder>('desc');

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const list = await bindingsApi.list();
      setBindings(list);
    } catch (e) {
      setError('לא הצלחנו לטעון את רשימת המכשירים');
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleSort = (col: SortBy) => {
    const isAsc = orderBy === col && order === 'asc';
    setOrder(isAsc ? 'desc' : 'asc');
    setOrderBy(col);
  };

  const sortedBindings = [...bindings].sort((a, b) => {
    let cmp = 0;
    if (orderBy === 'ip') {
      cmp = (a.ip || '').localeCompare(b.ip || '');
    } else if (orderBy === 'created_at') {
      cmp = (a.created_at || 0) - (b.created_at || 0);
    } else {
      cmp = (a.last_used_at ?? 0) - (b.last_used_at ?? 0);
    }
    return order === 'asc' ? cmp : -cmp;
  });

  const handleRemove = async (id: number) => {
    if (!window.confirm('להסיר את המכשיר מהחשבון? בפעם הבאה שתגלוש ממנו, תתבקש שוב לחבר אותו.')) return;
    try {
      await bindingsApi.remove(id);
      await load();
    } catch (e) {
      setError('ההסרה נכשלה – נסה שוב');
      console.error(e);
    }
  };

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" component="h1" sx={{ fontWeight: 600, mb: 1 }}>
          המכשירים שלי
        </Typography>
        <Typography variant="body2" color="text.secondary">
          מכשירים שמחוברים לחשבון. כשאתה גולש מהם ההגדרות שלך חלות. הסרת מכשיר תדרוש חיבור מחדש בפעם הבאה.
        </Typography>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      <Paper>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell sortDirection={orderBy === 'ip' ? order : false}>
                  <TableSortLabel active={orderBy === 'ip'} direction={orderBy === 'ip' ? order : 'asc'} onClick={() => handleSort('ip')}>
                    מזהה המכשיר (IP)
                  </TableSortLabel>
                </TableCell>
                <TableCell sortDirection={orderBy === 'created_at' ? order : false}>
                  <TableSortLabel active={orderBy === 'created_at'} direction={orderBy === 'created_at' ? order : 'asc'} onClick={() => handleSort('created_at')}>
                    חובר בתאריך
                  </TableSortLabel>
                </TableCell>
                <TableCell sortDirection={orderBy === 'last_used_at' ? order : false}>
                  <TableSortLabel active={orderBy === 'last_used_at'} direction={orderBy === 'last_used_at' ? order : 'asc'} onClick={() => handleSort('last_used_at')}>
                    שימוש אחרון
                  </TableSortLabel>
                </TableCell>
                <TableCell align="left">פעולה</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={4}>טוען...</TableCell>
                </TableRow>
              ) : bindings.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4}>עדיין לא חיברת מכשירים. כשתגלוש תופנה לדף לחיבור המכשיר.</TableCell>
                </TableRow>
              ) : (
                sortedBindings.map((b) => (
                  <TableRow key={b.id} hover sx={{ '&:hover': { bgcolor: 'action.selected' } }}>
                    <TableCell component="code" sx={{ fontFamily: 'monospace' }}>
                      {b.ip}
                    </TableCell>
                    <TableCell>{new Date(b.created_at * 1000).toLocaleDateString('he-IL')}</TableCell>
                    <TableCell>
                      {b.last_used_at
                        ? new Date(b.last_used_at * 1000).toLocaleString('he-IL', {
                            dateStyle: 'short',
                            timeStyle: 'short',
                          })
                        : '—'}
                    </TableCell>
                    <TableCell align="left">
                      <IconButton size="small" color="error" onClick={() => handleRemove(b.id)} title="להסיר מכשיר מהחשבון">
                        <DeleteIcon />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>
    </Container>
  );
};

export default ConnectionsPage;
