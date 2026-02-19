/**
 * צפייה בהקלטת תעבורה לפי קישור – דורש התחברות. כל משתמש מחובר יכול לצפות.
 * רק מנהלים רואים כפתורי הוספה לרשימה הגלובלית.
 */
import React, { useMemo, useState, useEffect, useCallback } from 'react';
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
  Button,
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
  Add as AddIcon,
  Public as PublicIcon,
} from '@mui/icons-material';
import { trafficApi, type TrafficLogEntry } from '../api/traffic';
import { useAuthStore } from '../store/authStore';
import { adminApi, type GlobalRule } from '../api/admin';

function getDomainOnlyUrl(url: string): string {
  try {
    const u = new URL(url.startsWith('http') ? url : 'https://' + url);
    return u.origin;
  } catch {
    return url;
  }
}

function ruleDisplayUrl(rule: GlobalRule): string {
  return rule.display_url || `${rule.domain_pattern}${rule.path_pattern || ''}`;
}

function actionLabel(action: string): string {
  return action === 'allow' ? 'פתיחה' : action === 'block' ? 'חסימה' : action;
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

const TrafficViewPage: React.FC = () => {
  const { user } = useAuthStore();
  const isAdmin = Boolean(user?.is_admin);
  const { token } = useParams<{ token: string }>();
  const [data, setData] = useState<{ started_at: number; ended_at: number | null; entries: TrafficLogEntry[] } | null>(null);
  const [loading, setLoading] = useState(true);
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
    <Container maxWidth="lg" sx={{ mt: { xs: 2, sm: 4 }, mb: 4, px: { xs: 0 } }} className="page-section container-content">
      <Box className="page-title-section" sx={{ mb: 3 }}>
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

        {addRuleError && (
          <Alert severity="error" onClose={() => setAddRuleError('')} sx={{ mx: 2, mb: 1 }}>
            {addRuleError}
          </Alert>
        )}

        {lastAddedRule && (
          <Alert severity="success" onClose={() => setLastAddedRule(null)} sx={{ mx: 2, mb: 1 }}>
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

        <TableContainer sx={{ maxHeight: '75vh', overflow: 'auto', scrollBehavior: 'smooth' }}>
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
    </Container>
  );
};

export default TrafficViewPage;
