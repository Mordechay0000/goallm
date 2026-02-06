/**
 * צפייה בהקלטת תעבורה לפי קישור – גישה ציבורית (כל מי שיש לו את הקישור).
 */
import React, { useMemo, useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
  Box,
  Container,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  TextField,
  InputAdornment,
  Checkbox,
  FormControlLabel,
  IconButton,
  Tooltip,
  Chip,
  Alert,
} from '@mui/material';
import {
  Search as SearchIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  CheckCircle as CheckCircleIcon,
  Info as InfoIcon,
} from '@mui/icons-material';
import { trafficApi, type TrafficLogEntry } from '../api/traffic';

const STATUS_LABELS: Record<string, string> = {
  open: 'פתוח',
  blocked: 'חסום',
  review: 'בדיקה / דף לא ברשימה',
  cert_missing: 'חוסר בתעודת אבטחה',
  error: 'שגיאה',
  custom_block: 'חסימה מותאמת',
  video_unchecked: 'וידאו שלא נבדק',
  other: 'אחר',
};

function statusLabel(s: string): string {
  return STATUS_LABELS[s] ?? s;
}

function statusIcon(status: string) {
  switch (status) {
    case 'blocked':
    case 'cert_missing':
    case 'error':
      return <ErrorIcon fontSize="small" color="error" />;
    case 'review':
    case 'custom_block':
    case 'video_unchecked':
      return <WarningIcon fontSize="small" sx={{ color: 'warning.main' }} />;
    default:
      return <CheckCircleIcon fontSize="small" color="success" />;
  }
}

const TrafficViewPage: React.FC = () => {
  const { token } = useParams<{ token: string }>();
  const [data, setData] = useState<{ started_at: number; ended_at: number | null; entries: TrafficLogEntry[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [advancedView, setAdvancedView] = useState(true);
  const [showUnblocked, setShowUnblocked] = useState(true);
  const [showBlockedOnly, setShowBlockedOnly] = useState(false);
  const [orderBy, setOrderBy] = useState<'url' | 'status' | 'time'>('url');
  const [order, setOrder] = useState<'asc' | 'desc'>('asc');

  useEffect(() => {
    if (!token) {
      setError('חסר קישור להקלטה');
      setLoading(false);
      return;
    }
    setLoading(true);
    setError('');
    trafficApi
      .viewByToken(token)
      .then((res) => {
        setData({
          started_at: res.started_at,
          ended_at: res.ended_at,
          entries: res.entries,
        });
      })
      .catch(() => {
        setError('הקלטה לא נמצאה או שהקישור לא תקין.');
      })
      .finally(() => setLoading(false));
  }, [token]);

  const filteredRows = useMemo(() => {
    if (!data) return [];
    let list = data.entries;
    const q = search.trim().toLowerCase();
    if (q) list = list.filter((r) => r.url.toLowerCase().includes(q));
    if (showBlockedOnly) list = list.filter((r) => r.status !== 'open');
    if (!showUnblocked) list = list.filter((r) => r.status !== 'open');
    return [...list].sort((a, b) => {
      let cmp = 0;
      if (orderBy === 'url') cmp = (a.url || '').localeCompare(b.url || '');
      else if (orderBy === 'status') cmp = (a.status || '').localeCompare(b.status || '');
      else cmp = (a.time_sec ?? 0) - (b.time_sec ?? 0);
      return order === 'asc' ? cmp : -cmp;
    });
  }, [data, search, showUnblocked, showBlockedOnly, orderBy, order]);

  if (loading) {
    return (
      <Box sx={{ p: 4, textAlign: 'center' }}>
        <Typography>טוען...</Typography>
      </Box>
    );
  }

  if (error || !data) {
    return (
      <Box sx={{ p: 4 }}>
        <Alert severity="error">{error || 'לא נמצאה הקלטה'}</Alert>
      </Box>
    );
  }

  const started = new Date(data.started_at * 1000).toLocaleString('he-IL');
  const ended = data.ended_at ? new Date(data.ended_at * 1000).toLocaleString('he-IL') : '—';

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" component="h1" sx={{ fontWeight: 600, mb: 1 }}>
          צפייה בהקלטת תעבורה
        </Typography>
        <Typography variant="body2" color="text.secondary">
        התחלה: {started} · סיום: {ended} · {data.entries.length} רשומות
        </Typography>
      </Box>

      <Paper>
        <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 2 }}>
          <FormControlLabel
            control={<Checkbox checked={advancedView} onChange={(e) => setAdvancedView(e.target.checked)} />}
            label="תצוגה מתקדמת"
          />
          <FormControlLabel
            control={<Checkbox checked={showUnblocked} onChange={(e) => setShowUnblocked(e.target.checked)} />}
            label="הצג גם שורות ללא חסימה"
          />
          <FormControlLabel
            control={<Checkbox checked={showBlockedOnly} onChange={(e) => setShowBlockedOnly(e.target.checked)} />}
            label="הצג רק חסומים"
          />
          <TextField
            size="small"
            placeholder="חיפוש"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            sx={{ minWidth: 200, mr: 'auto' }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
            }}
          />
          <Typography variant="body2" color="text.secondary">
            {filteredRows.length} שורות מוצגות מתוך {data.entries.length}
          </Typography>
        </Box>

        <TableContainer sx={{ maxHeight: '75vh' }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 600, width: 56 }}>#</TableCell>
                <TableCell sx={{ fontWeight: 600, width: 48 }} />
                {advancedView && (
                  <TableCell sx={{ fontWeight: 600, minWidth: 70 }}>פרוטוקול</TableCell>
                )}
                <TableCell sx={{ fontWeight: 600 }} sortDirection={orderBy === 'url' ? order : false}>
                  <TableSortLabel active={orderBy === 'url'} direction={orderBy === 'url' ? order : 'asc'} onClick={() => { setOrderBy('url'); setOrder(orderBy === 'url' && order === 'asc' ? 'desc' : 'asc'); }}>
                    כתובת (URL)
                  </TableSortLabel>
                </TableCell>
                <TableCell sx={{ fontWeight: 600, minWidth: 160 }} sortDirection={orderBy === 'status' ? order : false}>
                  <TableSortLabel active={orderBy === 'status'} direction={orderBy === 'status' ? order : 'asc'} onClick={() => { setOrderBy('status'); setOrder(orderBy === 'status' && order === 'asc' ? 'desc' : 'asc'); }}>
                    מצב / סיבת חסימה
                  </TableSortLabel>
                </TableCell>
                <TableCell sx={{ fontWeight: 600, width: 90 }} sortDirection={orderBy === 'time' ? order : false}>
                  <TableSortLabel active={orderBy === 'time'} direction={orderBy === 'time' ? order : 'asc'} onClick={() => { setOrderBy('time'); setOrder(orderBy === 'time' && order === 'asc' ? 'desc' : 'asc'); }}>
                    זמן
                  </TableSortLabel>
                </TableCell>
                {advancedView && (
                  <TableCell sx={{ fontWeight: 600, minWidth: 140 }}>סוג תוכן</TableCell>
                )}
                <TableCell sx={{ width: 40 }} />
              </TableRow>
            </TableHead>
            <TableBody>
              {filteredRows.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={advancedView ? 7 : 5} align="center" sx={{ py: 4 }}>
                    לא נמצאו שורות לפי הסינון.
                  </TableCell>
                </TableRow>
              ) : (
                filteredRows.map((row, idx) => (
                  <TableRow key={row.id} hover sx={{ '&:hover': { bgcolor: 'action.selected' } }}>
                    <TableCell>{idx + 1}</TableCell>
                    <TableCell>{statusIcon(row.status)}</TableCell>
                    {advancedView && (
                      <TableCell>
                        <Chip label={row.protocol || '—'} size="small" variant="outlined" sx={{ fontFamily: 'monospace' }} />
                      </TableCell>
                    )}
                    <TableCell sx={{ maxWidth: 320, overflow: 'hidden', textOverflow: 'ellipsis' }} title={row.url}>
                      {row.url}
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={statusLabel(row.status)}
                        size="small"
                        color={row.status === 'open' ? 'success' : row.status === 'blocked' || row.status === 'cert_missing' || row.status === 'error' ? 'error' : 'warning'}
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell>
                      {row.time_sec != null && row.time_sec >= 0 ? `${row.time_sec.toFixed(3)} s` : '—'}
                    </TableCell>
                    {advancedView && (
                      <TableCell sx={{ color: 'text.secondary', fontSize: '0.8rem' }}>{row.content_type || '—'}</TableCell>
                    )}
                    <TableCell>
                      <Tooltip title="פרטים">
                        <IconButton size="small">
                          <InfoIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
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

export default TrafficViewPage;
