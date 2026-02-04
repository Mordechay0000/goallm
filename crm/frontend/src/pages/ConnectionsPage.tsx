/**
 * חיבורים (שיוכי IP) – הצגת כל המכשירים המשויכים לחשבון ואפשרות לבטל שיוך.
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
  Alert,
} from '@mui/material';
import { Delete as DeleteIcon } from '@mui/icons-material';
import { bindingsApi, type IpBinding } from '../api/bindings';

const ConnectionsPage: React.FC = () => {
  const [bindings, setBindings] = useState<IpBinding[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');

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
    <Container maxWidth="md" sx={{ py: 3 }}>
      <Typography variant="h5" fontWeight={600} gutterBottom>
        המכשירים שמחוברים לחשבון שלי
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        אלה המכשירים שכבר חיברת לחשבון. כשאתה גולש מהם, ההגדרות שלך חלות אוטומטית. אם תסיר מכשיר – בפעם הבאה שתגלוש ממנו תתבקש לחבר אותו שוב.
      </Typography>

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
                <TableCell>מזהה המכשיר (IP)</TableCell>
                <TableCell>חובר בתאריך</TableCell>
                <TableCell>שימוש אחרון</TableCell>
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
                bindings.map((b) => (
                  <TableRow key={b.id}>
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
