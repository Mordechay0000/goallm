/**
 * הקלטת תעבורה – התחל/סיום רק כשהדף פתוח. סגירת הדף מפסיקה את ההקלטה אוטומטית.
 */
import React, { useMemo, useState, useEffect, useCallback, useRef } from 'react';
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
  Button,
  Alert,
} from '@mui/material';
import {
  Search as SearchIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  CheckCircle as CheckCircleIcon,
  Info as InfoIcon,
  FiberManualRecord as RecordIcon,
  Stop as StopIcon,
  ContentCopy as CopyIcon,
  OpenInNew as OpenInNewIcon,
} from '@mui/icons-material';
import { trafficApi, stopTrafficOnPageUnload, type TrafficLogEntry } from '../api/traffic';

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

const TrafficRecordingPage: React.FC = () => {
  const [recording, setRecording] = useState(false);
  const [entries, setEntries] = useState<TrafficLogEntry[]>([]);
  const [viewLink, setViewLink] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [statusPolling, setStatusPolling] = useState(false);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [advancedView, setAdvancedView] = useState(true);
  const [showUnblocked, setShowUnblocked] = useState(true);
  const [showBlockedOnly, setShowBlockedOnly] = useState(false);
  const [orderBy, setOrderBy] = useState<'url' | 'status' | 'time'>('url');
  const [order, setOrder] = useState<'asc' | 'desc'>('asc');
  const recordingRef = useRef(false);

  const fetchStatus = useCallback(async () => {
    try {
      const { recording: rec } = await trafficApi.status();
      setRecording(rec);
      recordingRef.current = rec;
    } catch (e) {
      setError('לא ניתן לטעון סטטוס הקלטה');
    }
  }, []);

  const fetchLog = useCallback(async (sessionId: number) => {
    setLoading(true);
    setError('');
    try {
      const { entries: list } = await trafficApi.log(sessionId);
      setEntries(list);
    } catch (e) {
      setError('לא ניתן לטעון לוג ההקלטה');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  useEffect(() => {
    recordingRef.current = recording;
  }, [recording]);

  useEffect(() => {
    const stopOnUnload = () => {
      if (recordingRef.current) stopTrafficOnPageUnload();
    };
    window.addEventListener('beforeunload', stopOnUnload);
    window.addEventListener('pagehide', stopOnUnload);
    return () => {
      window.removeEventListener('beforeunload', stopOnUnload);
      window.removeEventListener('pagehide', stopOnUnload);
    };
  }, []);

  useEffect(() => {
    if (!statusPolling || !recording) return;
    const t = setInterval(fetchStatus, 3000);
    return () => clearInterval(t);
  }, [statusPolling, recording, fetchStatus]);

  const handleStart = async () => {
    setError('');
    setLoading(true);
    try {
      await trafficApi.start();
      setRecording(true);
      recordingRef.current = true;
      setStatusPolling(true);
      await fetchStatus();
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string } } };
      setError(ax?.response?.data?.detail || 'התחלת ההקלטה נכשלה');
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    setError('');
    setLoading(true);
    setViewLink(null);
    try {
      const { session_id, share_token } = await trafficApi.stop();
      setRecording(false);
      recordingRef.current = false;
      setStatusPolling(false);
      setViewLink(trafficApi.getViewUrl(share_token));
      await fetchLog(session_id);
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string } } };
      setError(ax?.response?.data?.detail || 'סיום ההקלטה נכשל');
    } finally {
      setLoading(false);
    }
  };

  const copyViewLink = () => {
    if (viewLink) navigator.clipboard.writeText(viewLink);
  };

  const filteredRows = useMemo(() => {
    let list = entries;
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
  }, [entries, search, showUnblocked, showBlockedOnly, orderBy, order]);

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" component="h1" sx={{ fontWeight: 600, mb: 1 }}>
          הקלטת תעבורה
        </Typography>
        <Typography variant="body2" color="text.secondary">
          התחל הקלטה וגלוש דרך המכשירים המשויכים. סיום הקלטה או סגירת הדף מפסיקים את ההקלטה. המצב לא נשמר – רק כשהדף פתוח.
        </Typography>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      <Paper sx={{ p: 2, mb: 3 }}>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 2 }}>
          {!recording ? (
            <Button
              variant="contained"
              color="primary"
              startIcon={<RecordIcon />}
              onClick={handleStart}
              disabled={loading}
            >
              התחל הקלטה
            </Button>
          ) : (
            <Button
              variant="contained"
              color="error"
              startIcon={<StopIcon />}
              onClick={handleStop}
              disabled={loading}
            >
              סיום הקלטה
            </Button>
          )}
          {recording && (
            <Chip icon={<RecordIcon />} label="הקלטה פעילה – גלוש דרך המכשירים המשויכים. סגירת הדף תפסיק את ההקלטה" color="error" size="small" />
          )}
        </Box>
      </Paper>

      {viewLink && (
        <Paper sx={{ p: 2, mb: 3 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
            קישור להקלטה (כל מי שיש לו את הקישור יכול לצפות)
          </Typography>
          <TextField
            fullWidth
            size="small"
            value={viewLink}
            inputProps={{ readOnly: true }}
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <Button size="small" startIcon={<CopyIcon />} onClick={copyViewLink}>
                    העתק
                  </Button>
                  <Button size="small" startIcon={<OpenInNewIcon />} href={viewLink} target="_blank" rel="noopener noreferrer">
                    פתח קישור
                  </Button>
                </InputAdornment>
              ),
            }}
          />
        </Paper>
      )}

      {(entries.length > 0 || loading) && (
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
              {filteredRows.length} שורות מוצגות מתוך {entries.length}
            </Typography>
          </Box>

          {loading && entries.length === 0 ? (
            <Box sx={{ p: 4, textAlign: 'center' }}>טוען...</Box>
          ) : (
            <TableContainer sx={{ maxHeight: '70vh' }}>
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
                        {entries.length === 0 ? 'אין רשומות בהקלטה הזו' : 'לא נמצאו שורות לפי הסינון.'}
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
          )}
        </Paper>
      )}

      {!recording && entries.length === 0 && !loading && (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <RecordIcon sx={{ fontSize: 48, color: 'text.disabled', mb: 1 }} />
          <Typography color="text.secondary">
            לחץ על &quot;התחל הקלטה&quot;, גלוש דרך המכשירים המשויכים לחשבון, ואז &quot;סיום הקלטה&quot; כדי לראות את טבלת התעבורה.
          </Typography>
        </Paper>
      )}
    </Container>
  );
};

export default TrafficRecordingPage;
