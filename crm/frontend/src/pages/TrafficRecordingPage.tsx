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
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
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
import { useAuthStore } from '../store/authStore';
import { adminApi, type GlobalRule } from '../api/admin';
import { Add as AddIcon, Public as PublicIcon } from '@mui/icons-material';

function ruleDisplayUrl(rule: GlobalRule): string {
  return rule.display_url || `${rule.domain_pattern}${rule.path_pattern || ''}`;
}

function actionLabel(action: string): string {
  return action === 'allow' ? 'פתיחה' : action === 'block' ? 'חסימה' : action;
}

/** מחזיר כתובת של הדומיין בלבד (ללא נתיב) – למשל https://docs.google.com */
function getDomainOnlyUrl(url: string): string {
  try {
    const u = new URL(url.startsWith('http') ? url : 'https://' + url);
    return u.origin;
  } catch {
    return url;
  }
}

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
  const { user } = useAuthStore();
  const isAdmin = Boolean(user?.is_admin);
  const [recording, setRecording] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [entries, setEntries] = useState<TrafficLogEntry[]>([]);
  const [viewLink, setViewLink] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [statusPolling, setStatusPolling] = useState(false);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [advancedView, setAdvancedView] = useState(false);
  const [showUnblocked, setShowUnblocked] = useState(true);
  const [showBlockedOnly, setShowBlockedOnly] = useState(false);
  const [orderBy, setOrderBy] = useState<'url' | 'status' | 'time'>('url');
  const [order, setOrder] = useState<'asc' | 'desc'>('asc');
  const [addRuleLoading, setAddRuleLoading] = useState<string | null>(null);
  const [addRuleError, setAddRuleError] = useState('');
  const [lastAddedRule, setLastAddedRule] = useState<GlobalRule | null>(null);
  const [addRuleDialog, setAddRuleDialog] = useState<{ url: string; isDomain: boolean } | null>(null);
  const recordingRef = useRef(false);

  const openAddExactDialog = useCallback((url: string) => {
    setAddRuleError('');
    setLastAddedRule(null);
    setAddRuleDialog({ url, isDomain: false });
  }, []);

  const openAddDomainDialog = useCallback((url: string) => {
    setAddRuleError('');
    setLastAddedRule(null);
    setAddRuleDialog({ url: getDomainOnlyUrl(url), isDomain: true });
  }, []);

  const closeAddRuleDialog = useCallback(() => setAddRuleDialog(null), []);

  const confirmAddRule = useCallback(async () => {
    if (!addRuleDialog) return;
    const { url } = addRuleDialog;
    setAddRuleLoading(url);
    try {
      const rule = await adminApi.createGlobalRule({ url, action: 'allow' });
      setLastAddedRule(rule);
      setAddRuleDialog(null);
      setAddRuleLoading(null);
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string } } };
      setAddRuleError(ax?.response?.data?.detail || 'הוספת הכלל נכשלה');
      setAddRuleLoading(null);
    }
  }, [addRuleDialog]);

  const fetchStatus = useCallback(async () => {
    try {
      const { recording: rec, session_id: sid } = await trafficApi.status();
      setRecording(rec);
      setActiveSessionId(sid ?? null);
      recordingRef.current = rec;
    } catch (e) {
      setError('לא ניתן לטעון סטטוס ההקלטה');
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

  useEffect(() => {
    if (!recording || activeSessionId == null) return;
    setEntries([]);
    let closed = false;
    trafficApi
      .log(activeSessionId)
      .then(({ entries: list }) => {
        if (!closed) setEntries(list);
      })
      .catch(() => {
        if (!closed) setError('לא ניתן לטעון לוג ההקלטה');
      });
    const closeWs = trafficApi.connectTrafficLive(
      (newEntries) => {
        if (!closed) setEntries((prev) => [...prev, ...newEntries]);
      },
      (msg) => {
        if (!closed) setError(msg);
      }
    );
    return () => {
      closed = true;
      closeWs();
    };
  }, [recording, activeSessionId]);

  const handleStart = async () => {
    setError('');
    setLoading(true);
    setEntries([]);
    setActiveSessionId(null);
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
      setActiveSessionId(null);
      setRecording(false);
      recordingRef.current = false;
      setStatusPolling(false);
      setViewLink(trafficApi.getViewUrl(share_token));
      await fetchLog(session_id);
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string } } };
      const detail = ax?.response?.data?.detail ?? 'סיום ההקלטה נכשל';
      setError(detail);
      setActiveSessionId(null);
      setRecording(false);
      recordingRef.current = false;
      setStatusPolling(false);
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
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }} className="page-section container-content">
      <Box className="page-title-section" sx={{ mb: 3 }}>
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

      {(recording || entries.length > 0 || loading) && (
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

          {addRuleError && (
            <Alert severity="error" onClose={() => setAddRuleError('')} sx={{ mb: 1 }}>
              {addRuleError}
            </Alert>
          )}

          {lastAddedRule && (
            <Alert severity="success" onClose={() => setLastAddedRule(null)} sx={{ mb: 1 }}>
              <Typography variant="body2" component="span" sx={{ fontWeight: 600 }}>
                נוסף כלל לרשימה הגלובלית:
              </Typography>
              <Typography variant="body2" component="span" sx={{ fontFamily: 'monospace', display: 'block', mt: 0.5 }}>
                {ruleDisplayUrl(lastAddedRule)}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                מצב: {actionLabel(lastAddedRule.action)}
              </Typography>
            </Alert>
          )}

          {loading && entries.length === 0 ? (
            <Box sx={{ p: 4, textAlign: 'center' }}>טוען...</Box>
          ) : (
            <TableContainer sx={{ maxHeight: '70vh', overflow: 'auto', scrollBehavior: 'smooth' }}>
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
                    {advancedView && (
                      <TableCell sx={{ fontWeight: 600, width: 100 }} sortDirection={orderBy === 'time' ? order : false}>
                        <TableSortLabel active={orderBy === 'time'} direction={orderBy === 'time' ? order : 'asc'} onClick={() => { setOrderBy('time'); setOrder(orderBy === 'time' && order === 'asc' ? 'desc' : 'asc'); }}>
                          משך הבקשה
                        </TableSortLabel>
                      </TableCell>
                    )}
                    {advancedView && (
                      <TableCell sx={{ fontWeight: 600, minWidth: 140 }}>סוג תוכן</TableCell>
                    )}
                    {isAdmin && (
                      <TableCell sx={{ fontWeight: 600, minWidth: 180 }}>הוספה לרשימה הגלובלית</TableCell>
                    )}
                    {advancedView && (
                      <TableCell sx={{ width: 40 }} />
                    )}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {filteredRows.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={4 + (advancedView ? 4 : 0) + (isAdmin ? 1 : 0)} align="center" sx={{ py: 4 }}>
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
                        <TableCell
                          title={row.url}
                          sx={{
                            maxWidth: 400,
                            overflowX: 'auto',
                            whiteSpace: 'nowrap',
                            scrollbarWidth: 'thin',
                            scrollbarColor: '#1e3a5f #e2e8f0',
                            '&::-webkit-scrollbar': { height: 8 },
                            '&::-webkit-scrollbar-track': { background: '#e2e8f0', borderRadius: 8 },
                            '&::-webkit-scrollbar-thumb': { background: '#1e3a5f', borderRadius: 8, border: '2px solid #e2e8f0' },
                            '&::-webkit-scrollbar-thumb:hover': { background: '#152a45' },
                          }}
                        >
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
                        {advancedView && (
                          <TableCell>
                            {row.time_sec != null && row.time_sec >= 0 ? `${row.time_sec.toFixed(3)} s` : '—'}
                          </TableCell>
                        )}
                        {advancedView && (
                          <TableCell sx={{ color: 'text.secondary', fontSize: '0.8rem' }}>{row.content_type || '—'}</TableCell>
                        )}
                        {isAdmin && (
                          <TableCell sx={{ whiteSpace: 'nowrap' }}>
                            <Tooltip title="הוסף פתיחה – הכתובת המדויקת (הקישור כמו שהוא)">
                              <span>
                                <Button
                                  size="small"
                                  variant="outlined"
                                  startIcon={<AddIcon />}
                                  disabled={addRuleLoading !== null}
                                  onClick={() => openAddExactDialog(row.url)}
                                >
                                  כתובת מדויקת
                                </Button>
                              </span>
                            </Tooltip>
                            <Tooltip title="הוסף פתיחה – כל הדומיין (בלי נתיב)">
                              <span>
                                <Button
                                  size="small"
                                  variant="outlined"
                                  startIcon={<PublicIcon />}
                                  disabled={addRuleLoading !== null}
                                  onClick={() => openAddDomainDialog(row.url)}
                                  sx={{ ml: 0.5 }}
                                >
                                  כל הדומיין
                                </Button>
                              </span>
                            </Tooltip>
                          </TableCell>
                        )}
                        {advancedView && (
                          <TableCell>
                            <Tooltip title="פרטים">
                              <IconButton size="small">
                                <InfoIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          </TableCell>
                        )}
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          )}

          <Dialog open={Boolean(addRuleDialog)} onClose={closeAddRuleDialog} maxWidth="sm" fullWidth>
            <DialogTitle>הוספת כלל לרשימה הגלובלית</DialogTitle>
            <DialogContent>
              {addRuleDialog && (
                <>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                    הכלל שייווסף:
                  </Typography>
                  <Typography variant="body1" sx={{ fontFamily: 'monospace', wordBreak: 'break-all', mb: 1 }}>
                    {addRuleDialog.url}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    מצב: פתיחה
                  </Typography>
                </>
              )}
            </DialogContent>
            <DialogActions sx={{ px: 3, pb: 2 }}>
              <Button onClick={closeAddRuleDialog}>ביטול</Button>
              <Button variant="contained" onClick={confirmAddRule} disabled={addRuleLoading !== null}>
                {addRuleLoading !== null ? 'מוסיף...' : 'אישור'}
              </Button>
            </DialogActions>
          </Dialog>
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
