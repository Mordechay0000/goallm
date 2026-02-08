/**
 * Rules table component - the heart of the system
 */
import React, { useState } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Chip,
  Box,
  TextField,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Checkbox,
  FormControlLabel,
  Alert,
  TableSortLabel,
  TablePagination,
  InputAdornment,
  Typography,
} from '@mui/material';
import { Delete as DeleteIcon, Download as DownloadIcon, Upload as UploadIcon, Lock as LockIcon, Search as SearchIcon } from '@mui/icons-material';
import { TagInput } from './TagInput';
import type { Rule } from '../api/rules';
import { rulesApi, resolverApi } from '../api/rules';
import type { ResolverTestUrlResponse } from '../api/rules';
import { formatRuleDisplay } from '../utils/urlParser';
import { validateDomainOrUrl, processUrlInput } from '../utils/validation';

interface RulesTableProps {
  profileId: number;
  rules: Rule[];
  onRefresh: () => void;
  managedUserId?: number;
  /** When true (admin locked rules for this user), disable add/delete and show lock message */
  rulesLocked?: boolean;
}

const ACTION_LABELS: Record<string, string> = {
  block: 'חסום',
  allow: 'אפשר',
};

type RuleOrder = 'asc' | 'desc';
type RuleSortBy = 'domain' | 'action';
const ROWS_PER_PAGE_OPTIONS = [10, 25, 50, 100];

function stableSort<T>(arr: T[], cmp: (a: T, b: T) => number): T[] {
  return [...arr].sort(cmp);
}

export const RulesTable: React.FC<RulesTableProps> = ({ profileId, rules, onRefresh, managedUserId, rulesLocked }) => {
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);
  const [order, setOrder] = useState<RuleOrder>('asc');
  const [orderBy, setOrderBy] = useState<RuleSortBy>('domain');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [search, setSearch] = useState('');
  const [checkUrl, setCheckUrl] = useState('');
  const [checkResult, setCheckResult] = useState<ResolverTestUrlResponse | null | 'loading' | 'invalid'>(null);
  const [checkError, setCheckError] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  
  // Add rule form
  const [newUrl, setNewUrl] = useState('');
  const [newAction, setNewAction] = useState<'block' | 'allow'>('block');
  const [includeSubdomains, setIncludeSubdomains] = useState(false);
  const [newTagsList, setNewTagsList] = useState<string[]>([]);
  const [urlError, setUrlError] = useState<string>('');

  const handleAddRule = async () => {
    if (!newUrl.trim()) return;
    const err = validateDomainOrUrl(newUrl);
    if (err) {
      setUrlError(err);
      return;
    }
    
    try {
      await rulesApi.create(profileId, {
        url: newUrl,
        action: newAction,
        include_subdomains: includeSubdomains,
        tags: newTagsList.length > 0 ? newTagsList : undefined,
      }, managedUserId);
      setNewUrl('');
      setIncludeSubdomains(false);
      setNewTagsList([]);
      setNewAction('block');
      setUrlError('');
      onRefresh();
    } catch (err: unknown) {
      alert(`שגיאה: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  const handleDeleteRule = async (id: number) => {
    try {
      await rulesApi.delete(id, managedUserId);
      setDeleteConfirm(null);
      onRefresh();
    } catch (err: unknown) {
      alert(`שגיאה: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  const handleUrlChange = (value: string) => {
    const { cleaned, setSubdomains } = processUrlInput(value);
    setNewUrl(cleaned);
    setUrlError(validateDomainOrUrl(cleaned));
    if (setSubdomains) setIncludeSubdomains(true);
  };

  const handleSubdomainChange = (checked: boolean) => {
    setIncludeSubdomains(checked);
  };

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleAddRule();
  };

  const handleCheckUrl = async () => {
    const u = checkUrl.trim();
    setCheckError(null);
    if (!u) {
      setCheckResult(null);
      return;
    }
    const err = validateDomainOrUrl(u);
    if (err) {
      setCheckResult('invalid');
      setCheckError(err);
      return;
    }
    setCheckResult('loading');
    try {
      const res = await resolverApi.testUrl(u, 'html');
      setCheckResult(res);
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string } } };
      setCheckError(ax?.response?.data?.detail ?? 'שגיאה בבדיקה');
      setCheckResult('invalid');
    }
  };

  const handleExportCsv = async () => {
    try {
      await rulesApi.exportCsv(profileId, managedUserId);
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string } } };
      alert(ax?.response?.data?.detail || 'שגיאה בייצוא');
    }
  };

  const handleImportCsv = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    try {
      const result = await rulesApi.importCsv(profileId, file, managedUserId);
      onRefresh();
      alert(`יובאו ${result.imported} כללים`);
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string | { errors?: unknown; message?: string } } } };
      const detail = ax?.response?.data?.detail;
      const fallback = err instanceof Error ? err.message : 'שגיאה בייבוא';
      const msg = typeof detail === 'object' && detail && 'errors' in detail
        ? ((detail as { message?: string }).message ?? 'שגיאה') + ': ' + JSON.stringify((detail as { errors?: unknown }).errors)
        : (typeof detail === 'string' ? detail : fallback);
      alert(msg);
    } finally {
      setImporting(false);
      e.target.value = '';
    }
  };

  return (
    <Box>
      {rulesLocked && (
        <Alert severity="info" sx={{ mb: 2 }} icon={<LockIcon />}>
          ניהול כללים נחסם על ידי ההנהלה
        </Alert>
      )}
      <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 1, mb: 2 }}>
        <Button variant="outlined" size="small" startIcon={<DownloadIcon />} onClick={handleExportCsv} disabled={rulesLocked}>
          ייצא CSV
        </Button>
        <Button variant="outlined" size="small" startIcon={<UploadIcon />} onClick={() => fileInputRef.current?.click()} disabled={importing || rulesLocked}>
          {importing ? 'מייבא...' : 'ייבא CSV'}
        </Button>
        <input type="file" ref={fileInputRef} accept=".csv" style={{ display: 'none' }} onChange={handleImportCsv} />
      </Box>
      {/* Add Rule Form */}
      <Paper sx={{ p: 2, mb: 2 }} style={rulesLocked ? { opacity: 0.7, pointerEvents: 'none' } : undefined}>
        <Box className="card-header-accent" sx={{ mb: 2 }}>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>הוספת כלל</Typography>
        </Box>
        <form onSubmit={handleFormSubmit}>
          <Box sx={{ mb: 2 }}>
            <TextField
              fullWidth
              label="כתובת אתר (URL)"
              value={newUrl}
              onChange={(e) => handleUrlChange(e.target.value)}
              placeholder="example.com/path או *.example.com"
              helperText={urlError || "הזן כתובת מלאה. פרוטוקול ו־*. יוסרו אוטומטית"}
              error={!!urlError}
              sx={{ mb: 1 }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  if (!urlError && newUrl.trim()) {
                    handleAddRule();
                  }
                }
              }}
            />
          <FormControlLabel
            control={
              <Checkbox
                checked={includeSubdomains}
                onChange={(e) => handleSubdomainChange(e.target.checked)}
              />
            }
            label="כולל סאב-דומיינים"
          />
          <Box sx={{ mt: 1 }}>
            <TagInput
              value={newTagsList}
              onChange={setNewTagsList}
              helperText="תגיות לאתר – משמשות לכללי תגיות. הקלד תגית והקש פסיק או Enter"
              disabled={!!rulesLocked}
            />
          </Box>
        </Box>

        <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
          <FormControl sx={{ minWidth: 120 }}>
            <InputLabel>פעולה</InputLabel>
            <Select
              value={newAction}
              onChange={(e) => setNewAction(e.target.value as 'block' | 'allow')}
              label="פעולה"
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  if (!urlError && newUrl.trim()) {
                    handleAddRule();
                  }
                }
              }}
            >
              <MenuItem value="block">חסום</MenuItem>
              <MenuItem value="allow">אפשר</MenuItem>
            </Select>
          </FormControl>

          <Button
            type="submit"
            variant="contained"
            color="secondary"
            disabled={!newUrl.trim() || !!urlError}
          >
            הוסף כלל
          </Button>
        </Box>
        </form>

      </Paper>

      {/* Rules Table */}
      <Paper>
        <Box className="card-header-accent" sx={{ px: 2, pt: 2, pb: 1 }}>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>כללי הסינון</Typography>
        </Box>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 1, px: 2, pt: 2, pb: 1 }}>
          <TextField
            size="small"
            placeholder="בדוק URL – איזה כלל חל? (משתמש באותה לוגיקה כמו הסינון)"
            value={checkUrl}
            onChange={(e) => { setCheckUrl(e.target.value); setCheckResult(null); setCheckError(null); }}
            onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleCheckUrl())}
            sx={{ minWidth: 320 }}
          />
          <Button variant="outlined" size="small" onClick={() => handleCheckUrl()} disabled={!checkUrl.trim() || checkResult === 'loading'}>
            {checkResult === 'loading' ? 'בודק...' : 'בדוק'}
          </Button>
          {checkResult === 'invalid' && checkError && (
            <Typography variant="body2" color="error">{checkError}</Typography>
          )}
          {checkResult && checkResult !== 'invalid' && checkResult !== 'loading' && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
              {checkResult.rule ? (
                <>
                  <Typography variant="body2" color="text.secondary">הכלל החל:</Typography>
                  <Chip size="small" label={(checkResult.rule.domain || '') + (checkResult.rule.path || '')} sx={{ fontFamily: 'monospace' }} />
                  <Chip size="small" variant="outlined" label={ACTION_LABELS[checkResult.rule.state as 'allow' | 'block'] ?? checkResult.rule.state} color={checkResult.rule.state === 'block' ? 'default' : 'secondary'} />
                </>
              ) : (
                <>
                  <Typography variant="body2" color="text.secondary">אין כלל מתאים</Typography>
                  <Typography variant="body2" color="text.secondary">
                    ({checkResult.default_mode === 'whitelist' ? 'הכל חסום – אוסיף פתיחות' : 'הכל פתוח – אוסיף חסימות'} → {checkResult.state === 'review' ? 'נשלח לבדיקה' : 'פתוח'})
                  </Typography>
                </>
              )}
            </Box>
          )}
        </Box>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 1, px: 2, pb: 2 }}>
          <TextField
            size="small"
            placeholder="חיפוש כללים (כתובת, דומיין)..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(0); }}
            sx={{ minWidth: 240 }}
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
                <TableCell sortDirection={orderBy === 'domain' ? order : false}>
                  <TableSortLabel active={orderBy === 'domain'} direction={orderBy === 'domain' ? order : 'asc'} onClick={() => { setOrderBy('domain'); setOrder(orderBy === 'domain' && order === 'asc' ? 'desc' : 'asc'); setPage(0); }}>
                    כתובת
                  </TableSortLabel>
                </TableCell>
                <TableCell sortDirection={orderBy === 'action' ? order : false}>
                  <TableSortLabel active={orderBy === 'action'} direction={orderBy === 'action' ? order : 'asc'} onClick={() => { setOrderBy('action'); setOrder(orderBy === 'action' && order === 'asc' ? 'desc' : 'asc'); setPage(0); }}>
                    פעולה
                  </TableSortLabel>
                </TableCell>
                <TableCell>תגיות</TableCell>
                <TableCell align="center">פעולות</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(() => {
                const q = search.trim().toLowerCase();
                const filtered = !q
                  ? rules
                  : rules.filter((r) => ((r.domain_pattern || '') + (r.path_pattern || '')).toLowerCase().includes(q));
                if (filtered.length === 0) {
                  return (
                    <TableRow>
                      <TableCell colSpan={4} align="center">
                        {rules.length === 0 ? 'אין כללים' : 'אין תוצאות לחיפוש'}
                      </TableCell>
                    </TableRow>
                  );
                }
                const cmp = (a: Rule, b: Rule) => {
                  let v = 0;
                  if (orderBy === 'domain') v = ((a.domain_pattern || '') + (a.path_pattern || '')).localeCompare((b.domain_pattern || '') + (b.path_pattern || ''));
                  else v = (a.action || '').localeCompare(b.action || '');
                  return order === 'asc' ? v : -v;
                };
                const sorted = stableSort(filtered, cmp);
                const paginated = sorted.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage);
                return paginated.map((rule) => (
                <TableRow key={rule.id} hover sx={{ '&:hover': { bgcolor: 'action.selected' } }}>
                  <TableCell
                    sx={{
                      maxWidth: 400,
                      overflowX: 'auto',
                      whiteSpace: 'nowrap',
                      scrollbarWidth: 'thin',
                      scrollbarColor: '#2F6CFF #E4E7EC',
                      '&::-webkit-scrollbar': { height: 8 },
                      '&::-webkit-scrollbar-track': { background: '#E4E7EC', borderRadius: 8 },
                      '&::-webkit-scrollbar-thumb': { background: '#2F6CFF', borderRadius: 8, border: '2px solid #E4E7EC' },
                      '&::-webkit-scrollbar-thumb:hover': { background: '#2555d9' },
                    }}
                  >
                    <code>{formatRuleDisplay(rule)}</code>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={ACTION_LABELS[rule.action]}
                      color={rule.action === 'block' ? 'error' : 'success'}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {(rule.tags || []).map((tag) => (
                        <Chip key={tag} label={tag} size="small" variant="outlined" />
                      ))}
                    </Box>
                  </TableCell>
                  <TableCell align="center">
                    <IconButton
                      size="small"
                      color="error"
                      onClick={() => setDeleteConfirm(rule.id)}
                      disabled={!!rulesLocked}
                      title={rulesLocked ? 'נעול על ידי ההנהלה' : 'מחק'}
                    >
                      <DeleteIcon />
                    </IconButton>
                  </TableCell>
                </TableRow>
                ));
              })()}
            </TableBody>
          </Table>
          {(() => {
            const q = search.trim().toLowerCase();
            const filtered = !q ? rules : rules.filter((r) => ((r.domain_pattern || '') + (r.path_pattern || '')).toLowerCase().includes(q));
            const n = filtered.length;
            return n > 0 ? (
              <TablePagination
                component="div"
                count={n}
                page={page}
                onPageChange={(_, p) => setPage(p)}
                rowsPerPage={rowsPerPage}
                onRowsPerPageChange={(e) => { setRowsPerPage(parseInt(e.target.value, 10)); setPage(0); }}
                rowsPerPageOptions={ROWS_PER_PAGE_OPTIONS}
                labelRowsPerPage="שורות בעמוד:"
                labelDisplayedRows={({ from, to, count }) => `${from}–${to} מתוך ${count}`}
              />
            ) : null;
          })()}
        </TableContainer>
      </Paper>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteConfirm !== null} onClose={() => setDeleteConfirm(null)}>
        <DialogTitle>מחיקת כלל</DialogTitle>
        <DialogContent>
          האם אתה בטוח שברצונך למחוק את הכלל הזה?
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteConfirm(null)}>ביטול</Button>
          <Button
            color="error"
            onClick={() => deleteConfirm !== null && handleDeleteRule(deleteConfirm)}
          >
            מחק
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};
