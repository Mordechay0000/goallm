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
  Collapse,
  Alert,
  TableSortLabel,
  TablePagination,
  InputAdornment,
} from '@mui/material';
import { Delete as DeleteIcon, ExpandMore as ExpandMoreIcon, Download as DownloadIcon, Upload as UploadIcon, Lock as LockIcon, Search as SearchIcon } from '@mui/icons-material';
import type { Rule } from '../api/rules';
import { rulesApi } from '../api/rules';
import { formatRuleDisplay } from '../utils/urlParser';

interface RulesTableProps {
  profileId: number;
  rules: Rule[];
  onRefresh: () => void;
  managedUserId?: number;
  /** When true (admin locked rules for this user), disable add/delete and show lock message */
  rulesLocked?: boolean;
}

const TYPE_LABELS: Record<string, string> = {
  '*': 'הכל',
  image: 'תמונה',
  video: 'וידאו',
};

const ACTION_LABELS: Record<string, string> = {
  block: 'חסום',
  allow: 'אפשר',
};

type RuleOrder = 'asc' | 'desc';
type RuleSortBy = 'domain' | 'action' | 'type';
const ROWS_PER_PAGE_OPTIONS = [10, 25, 50, 100];

function stableSort<T>(arr: T[], cmp: (a: T, b: T) => number): T[] {
  return [...arr].sort(cmp);
}

export const RulesTable: React.FC<RulesTableProps> = ({ profileId, rules, onRefresh, managedUserId, rulesLocked }) => {
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [order, setOrder] = useState<RuleOrder>('asc');
  const [orderBy, setOrderBy] = useState<RuleSortBy>('domain');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [search, setSearch] = useState('');
  const [importing, setImporting] = useState(false);
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  
  // Add rule form
  const [newUrl, setNewUrl] = useState('');
  const [newAction, setNewAction] = useState<'block' | 'allow'>('block');
  const [newType, setNewType] = useState<'*' | 'image' | 'video'>('*');
  const [includeSubdomains, setIncludeSubdomains] = useState(false);
  const [newTagsList, setNewTagsList] = useState<string[]>([]);
  const [newTagInput, setNewTagInput] = useState('');
  const [urlError, setUrlError] = useState<string>('');
  const tagInputRef = React.useRef<HTMLInputElement>(null);

  const validateUrl = (url: string): string => {
    if (!url.trim()) return '';
    
    // Remove protocol if present
    let cleanUrl = url.trim();
    if (cleanUrl.startsWith('http://')) {
      cleanUrl = cleanUrl.substring(7);
    } else if (cleanUrl.startsWith('https://')) {
      cleanUrl = cleanUrl.substring(8);
    }
    
    // Check for invalid patterns
    if (cleanUrl.includes('://')) {
      return 'כתובת לא תקינה - הסר את הפרוטוקול';
    }
    
    // Check for multiple slashes in a row (more than 2)
    if (/\/{3,}/.test(cleanUrl)) {
      return 'כתובת לא תקינה - יותר מדי לוכסנים';
    }
    
    // Check for invalid characters; control chars via charCode (no-control-regex)
    if (/[<>"|\\]/.test(cleanUrl)) return 'כתובת לא תקינה - תווים לא חוקיים';
    for (let i = 0; i < cleanUrl.length; i++) {
      const c = cleanUrl.charCodeAt(i);
      if (c <= 0x1f) return 'כתובת לא תקינה - תווים לא חוקיים';
    }
    
    // Check if starts with *.
    if (cleanUrl.startsWith('*.')) {
      cleanUrl = cleanUrl.substring(2);
    }
    
    // Basic domain validation
    if (cleanUrl.length === 0) {
      return 'כתובת לא תקינה - שדה ריק';
    }
    
    // Check for valid domain pattern
    const parts = cleanUrl.split('/');
    const domain = parts[0];
    
    if (domain.length === 0) {
      return 'כתובת לא תקינה - אין דומיין';
    }
    
    // Domain should contain at least one dot or be localhost
    if (!domain.includes('.') && domain !== 'localhost' && !domain.startsWith('*')) {
      // Allow IP addresses
      const ipPattern = /^(\d{1,3}\.){3}\d{1,3}$/;
      if (!ipPattern.test(domain)) {
        return 'כתובת לא תקינה - דומיין לא תקין';
      }
    }
    
    return '';
  };

  const handleAddRule = async () => {
    if (!newUrl.trim()) return;
    
    const error = validateUrl(newUrl);
    if (error) {
      setUrlError(error);
      return;
    }
    
    try {
      await rulesApi.create(profileId, {
        url: newUrl,
        action: newAction,
        type: newType,
        include_subdomains: includeSubdomains,
        tags: newTagsList.length > 0 ? newTagsList : undefined,
      }, managedUserId);
      setNewUrl('');
      setIncludeSubdomains(false);
      setNewTagsList([]);
      setNewTagInput('');
      setNewType('*');
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

  // Handle URL input - check for *. prefix
  const handleUrlChange = (value: string) => {
    setNewUrl(value);
    setUrlError(validateUrl(value));
    if (value.startsWith('*.')) {
      setIncludeSubdomains(true);
    } else if (value.startsWith('*')) {
      setIncludeSubdomains(true);
      setNewUrl(value.substring(1));
    }
  };

  // Handle subdomain checkbox
  const handleSubdomainChange = (checked: boolean) => {
    setIncludeSubdomains(checked);
    if (checked && !newUrl.startsWith('*.')) {
      const parts = newUrl.split('/', 1);
      if (parts[0]) {
        setNewUrl(`*.${parts[0]}${newUrl.includes('/') ? '/' + newUrl.split('/', 2)[1] : ''}`);
      }
    } else if (!checked && newUrl.startsWith('*.')) {
      setNewUrl(newUrl.substring(2));
    }
  };

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleAddRule();
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
        <form onSubmit={handleFormSubmit}>
          <Box sx={{ mb: 2 }}>
            <TextField
              fullWidth
              label="כתובת אתר (URL)"
              value={newUrl}
              onChange={(e) => handleUrlChange(e.target.value)}
              placeholder="example.com/path או *.example.com"
              helperText={urlError || "הזן כתובת מלאה. הפרוטוקול (http/https) יוסר אוטומטית"}
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
                disabled={newUrl.startsWith('*.')}
              />
            }
            label="כולל סאב-דומיינים"
          />
          <Box sx={{ mt: 1 }}>
            <Box
              component="label"
              sx={{
                display: 'block',
                fontSize: '0.75rem',
                color: 'text.secondary',
                mb: 0.5,
              }}
            >
              תגיות
            </Box>
            <Box
              sx={{
                display: 'flex',
                flexWrap: 'wrap',
                alignItems: 'center',
                gap: 0.5,
                minHeight: 40,
                p: 1,
                border: 1,
                borderColor: 'divider',
                borderRadius: 1,
                bgcolor: 'background.paper',
                '&:focus-within': {
                  borderColor: 'primary.main',
                  borderWidth: 2,
                  p: '7px',
                },
              }}
            >
              {newTagsList.map((tag, index) => (
                <Chip
                  key={`${tag}-${index}`}
                  label={tag}
                  size="small"
                  onDelete={() => setNewTagsList((prev) => prev.filter((_, i) => i !== index))}
                  sx={{ mr: 0.25 }}
                />
              ))}
              <TextField
                inputRef={tagInputRef}
                size="small"
                placeholder={newTagsList.length === 0 ? 'הקלד תגית והקש פסיק או Enter' : 'תגית...'}
                value={newTagInput}
                onChange={(e) => setNewTagInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === ',' || e.key === 'Enter') {
                    e.preventDefault();
                    const v = newTagInput.trim();
                    if (v && !newTagsList.includes(v)) {
                      setNewTagsList((prev) => [...prev, v]);
                      setNewTagInput('');
                    }
                  } else if (e.key === 'Backspace' && !newTagInput && newTagsList.length > 0) {
                    setNewTagsList((prev) => prev.slice(0, -1));
                  }
                }}
                sx={{
                  flex: 1,
                  minWidth: 120,
                  '& .MuiInputBase-root': { bgcolor: 'transparent' },
                  '& .MuiOutlinedInput-notchedOutline': { border: 'none' },
                }}
                inputProps={{ sx: { py: 0.5, px: 0.5 } }}
              />
            </Box>
            <Box component="span" sx={{ fontSize: '0.75rem', color: 'text.secondary', mt: 0.5, display: 'block' }}>
              תגיות לאתר – משמשות לכללי תגיות. הקלד תגית והקש פסיק או Enter; מחיקה מסירה תגית.
            </Box>
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
            color="primary"
            disabled={!newUrl.trim() || !!urlError}
          >
            הוסף כלל
          </Button>
        </Box>
        </form>

        {/* Advanced Settings */}
        <Collapse in={showAdvanced}>
          <Box sx={{ mt: 2 }}>
            <FormControl sx={{ minWidth: 120 }}>
              <InputLabel>סוג</InputLabel>
              <Select
                value={newType}
                onChange={(e) => setNewType(e.target.value as '*' | 'image' | 'video')}
                label="סוג"
              >
                <MenuItem value="*">הכל</MenuItem>
                <MenuItem value="image">תמונה</MenuItem>
                <MenuItem value="video">וידאו</MenuItem>
              </Select>
            </FormControl>
          </Box>
        </Collapse>

        <Button
          size="small"
          onClick={() => setShowAdvanced(!showAdvanced)}
          endIcon={<ExpandMoreIcon sx={{ transform: showAdvanced ? 'rotate(180deg)' : 'none' }} />}
        >
          הגדרות מתקדמות
        </Button>
      </Paper>

      {/* Rules Table */}
      <Paper>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 1, px: 2, pt: 2, pb: 1 }}>
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
                <TableCell sortDirection={orderBy === 'type' ? order : false}>
                  <TableSortLabel active={orderBy === 'type'} direction={orderBy === 'type' ? order : 'asc'} onClick={() => { setOrderBy('type'); setOrder(orderBy === 'type' && order === 'asc' ? 'desc' : 'asc'); setPage(0); }}>
                    סוג
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
                      <TableCell colSpan={5} align="center">
                        {rules.length === 0 ? 'אין כללים' : 'אין תוצאות לחיפוש'}
                      </TableCell>
                    </TableRow>
                  );
                }
                const cmp = (a: Rule, b: Rule) => {
                  let v = 0;
                  if (orderBy === 'domain') v = ((a.domain_pattern || '') + (a.path_pattern || '')).localeCompare((b.domain_pattern || '') + (b.path_pattern || ''));
                  else if (orderBy === 'action') v = (a.action || '').localeCompare(b.action || '');
                  else if (orderBy === 'type') v = (a.type || '').localeCompare(b.type || '');
                  return order === 'asc' ? v : -v;
                };
                const sorted = stableSort(filtered, cmp);
                const paginated = sorted.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage);
                return paginated.map((rule) => (
                <TableRow key={rule.id}>
                  <TableCell>
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
                    {rule.type !== '*' && (
                      <Chip label={TYPE_LABELS[rule.type]} size="small" variant="outlined" />
                    )}
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
