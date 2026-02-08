/**
 * Admin: manage global rules (base whitelist). Admin only.
 */
import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
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
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Checkbox,
  FormControlLabel,
  Chip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  TableSortLabel,
  TablePagination,
  InputAdornment,
  Alert,
} from '@mui/material';
import { Add as AddIcon, Delete as DeleteIcon, Edit as EditIcon, ExpandMore as ExpandMoreIcon, Search as SearchIcon } from '@mui/icons-material';
import { adminApi, type GlobalRule, type GlobalRuleCreate, type GlobalRuleUpdate } from '../api/admin';
import { TagInput } from '../components/TagInput';
import { validateDomainOrUrl, processUrlInput } from '../utils/validation';

const ACTION_LABELS: Record<string, string> = { block: 'חסום', allow: 'אפשר' };

type Order = 'asc' | 'desc';
type OrderBy = 'url' | 'action';
const ROWS_PER_PAGE_OPTIONS = [10, 25, 50, 100];

function stableSort<T>(arr: T[], cmp: (a: T, b: T) => number): T[] {
  return [...arr].sort(cmp);
}

function ruleDisplayUrl(r: GlobalRule): string {
  return r.display_url || (r.domain_pattern + (r.path_pattern || ''));
}

const AdminGlobalRulesPage: React.FC = () => {
  const [rules, setRules] = useState<GlobalRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [url, setUrl] = useState('');
  const [action, setAction] = useState<'allow' | 'block'>('allow');
  const [includeSubdomains, setIncludeSubdomains] = useState(false);
  const [tags, setTags] = useState<string[]>([]);
  const [textFilterEnabled, setTextFilterEnabled] = useState(true);
  const [imageFilterEnabled, setImageFilterEnabled] = useState(true);
  const [fileFilterEnabled, setFileFilterEnabled] = useState(true);
  const [urlError, setUrlError] = useState('');
  const [saving, setSaving] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);

  // Table: search, filter, sort, pagination
  const [search, setSearch] = useState('');
  const [filterAction, setFilterAction] = useState<string>('');
  const [order, setOrder] = useState<Order>('asc');
  const [orderBy, setOrderBy] = useState<OrderBy>('url');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);

  // URL resolve: which rule applies
  const [resolveUrl, setResolveUrl] = useState('');
  const [resolveResult, setResolveResult] = useState<GlobalRule | null | 'loading' | 'invalid'>(null);
  const [resolveError, setResolveError] = useState<string | null>(null);
  const [resolveDone, setResolveDone] = useState(false);

  const [editRuleIdError, setEditRuleIdError] = useState<string | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();

  const loadRules = async () => {
    setLoading(true);
    try {
      const list = await adminApi.listGlobalRules();
      setRules(list);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRules();
  }, []);

  // Open edit dialog when navigating from "בקשות שהתקבלו" with ?edit=ruleId
  useEffect(() => {
    const editId = searchParams.get('edit');
    if (!editId) return;
    const id = parseInt(editId, 10);
    if (Number.isNaN(id)) {
      setSearchParams((p) => {
        const next = new URLSearchParams(p);
        next.delete('edit');
        return next;
      }, { replace: true });
      return;
    }
    setEditRuleIdError(null);
    adminApi
      .getGlobalRule(id)
      .then((rule) => {
        setSearchParams((p) => {
          const next = new URLSearchParams(p);
          next.delete('edit');
          return next;
        }, { replace: true });
        openEdit(rule);
      })
      .catch((e: unknown) => {
        const status = e && typeof e === 'object' && 'response' in e && (e as { response?: { status?: number } }).response?.status;
        setEditRuleIdError(status === 404 ? 'הכלל לא קיים' : 'שגיאה בטעינת הכלל');
        setSearchParams((p) => {
          const next = new URLSearchParams(p);
          next.delete('edit');
          return next;
        }, { replace: true });
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams.get('edit')]);

  const openAdd = () => {
    setEditingId(null);
    setUrl('');
    setUrlError('');
    setAction('allow');
    setIncludeSubdomains(false);
    setTags([]);
    setTextFilterEnabled(true);
    setImageFilterEnabled(true);
    setFileFilterEnabled(true);
    setDialogOpen(true);
  };

  const openEdit = (r: GlobalRule) => {
    setEditingId(r.id);
    const u = r.display_url || (r.domain_pattern + (r.path_pattern || ''));
    setUrl(u);
    setUrlError(validateDomainOrUrl(u));
    setAction((r.action as 'allow' | 'block') || 'allow');
    setIncludeSubdomains(r.include_subdomains || false);
    setTags(r.tags || []);
    setTextFilterEnabled(r.text_filter_enabled !== false);
    setImageFilterEnabled(r.image_filter_enabled !== false);
    setFileFilterEnabled(r.file_filter_enabled !== false);
    setDialogOpen(true);
  };

  const handleSave = async () => {
    const u = url.trim();
    const err = validateDomainOrUrl(u);
    if (err) {
      setUrlError(err);
      return;
    }
    setSaving(true);
    try {
      const isAllow = action === 'allow';
      const tf = isAllow ? textFilterEnabled : undefined;
      const imgf = isAllow ? imageFilterEnabled : undefined;
      const filef = isAllow ? fileFilterEnabled : undefined;
      if (editingId) {
        const data: GlobalRuleUpdate = { url: u, action, include_subdomains: includeSubdomains, tags: tags.length ? tags : undefined, text_filter_enabled: tf, image_filter_enabled: imgf, file_filter_enabled: filef };
        await adminApi.updateGlobalRule(editingId, data);
      } else {
        const data: GlobalRuleCreate = { url: u, action, include_subdomains: includeSubdomains, tags: tags.length ? tags : undefined, text_filter_enabled: tf, image_filter_enabled: imgf, file_filter_enabled: filef };
        await adminApi.createGlobalRule(data);
      }
      setDialogOpen(false);
      setUrlError('');
      await loadRules();
    } catch (e: unknown) {
      const msg = e && typeof e === 'object' && 'response' in e && (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      alert(msg || 'שגיאה בשמירה');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await adminApi.deleteGlobalRule(id);
      setDeleteConfirm(null);
      await loadRules();
    } catch (e) {
      console.error(e);
    }
  };

  const handleResolveUrl = async () => {
    const u = resolveUrl.trim();
    setResolveError(null);
    if (!u) {
      setResolveResult(null);
      setResolveDone(false);
      return;
    }
    const err = validateDomainOrUrl(u);
    if (err) {
      setResolveResult('invalid');
      setResolveError(err);
      setResolveDone(true);
      return;
    }
    setResolveResult('loading');
    setResolveDone(false);
    try {
      const { rule } = await adminApi.resolveGlobalRule(u);
      setResolveResult(rule);
      setResolveDone(true);
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string } } };
      setResolveError(ax?.response?.data?.detail ?? 'שגיאה בבדיקה');
      setResolveResult('invalid');
      setResolveDone(true);
    }
  };

  // Filtered and sorted rules for table
  const filteredRules = (() => {
    let list = rules;
    const q = search.trim().toLowerCase();
    if (q) {
      list = list.filter((r) => ruleDisplayUrl(r).toLowerCase().includes(q));
    }
    if (filterAction) {
      list = list.filter((r) => (r.action || '') === filterAction);
    }
    return list;
  })();
  const cmp = (a: GlobalRule, b: GlobalRule) => {
    let v = 0;
    if (orderBy === 'url') v = ruleDisplayUrl(a).localeCompare(ruleDisplayUrl(b));
    else v = (a.action || '').localeCompare(b.action || '');
    return order === 'asc' ? v : -v;
  };
  const sortedRules = stableSort(filteredRules, cmp);
  const paginatedRules = sortedRules.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage);

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      {editRuleIdError && (
        <Alert severity="error" onClose={() => setEditRuleIdError(null)} sx={{ mb: 2 }}>
          {editRuleIdError}
        </Alert>
      )}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 2, mb: 3 }}>
        <Box>
          <Typography variant="h5" component="h1" sx={{ fontWeight: 600, mb: 1 }}>
            רשימה גלובלית
          </Typography>
          <Typography variant="body2" color="text.secondary">
            הרשימה הגלובלית קובעת אילו אתרים בכלל יכולים להיות פתוחים במערכת. רק אדמין יכול לערוך.
          </Typography>
        </Box>
        <Button variant="contained" color="secondary" startIcon={<AddIcon />} onClick={openAdd}>
          הוסף כלל
        </Button>
      </Box>

      {/* Resolve URL: which rule applies */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Box className="card-header-accent" sx={{ mb: 2 }}>
          <Typography variant="h6">בדיקת קישור – איזה כלל גלובלי חל?</Typography>
        </Box>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 1 }}>
          <TextField
            size="small"
            placeholder="הזן קישור (דומיין או URL מלא)"
            value={resolveUrl}
            onChange={(e) => { setResolveUrl(e.target.value); setResolveResult(null); setResolveError(null); setResolveDone(false); }}
            onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleResolveUrl())}
            sx={{ minWidth: 320 }}
          />
          <Button variant="outlined" size="small" onClick={handleResolveUrl} disabled={!resolveUrl.trim() || resolveResult === 'loading'}>
            {resolveResult === 'loading' ? 'בודק...' : 'בדוק'}
          </Button>
          {resolveResult === 'invalid' && resolveError && (
            <Typography variant="body2" color="error">{resolveError}</Typography>
          )}
          {resolveDone && resolveResult !== 'invalid' && resolveResult !== 'loading' && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
              {resolveResult && typeof resolveResult === 'object' ? (
                <>
                  <Typography variant="body2" color="text.secondary">הכלל החל:</Typography>
                  <Chip size="small" label={ruleDisplayUrl(resolveResult)} sx={{ fontFamily: 'monospace' }} />
                  <Chip size="small" variant="outlined" label={ACTION_LABELS[resolveResult.action] ?? resolveResult.action} color={resolveResult.action === 'block' ? 'default' : 'secondary'} />
                </>
              ) : (
                <Typography variant="body2" color="text.secondary">אין כלל גלובלי מתאים לכתובת זו</Typography>
              )}
            </Box>
          )}
        </Box>
      </Paper>

      <Paper>
        <Box className="card-header-accent" sx={{ px: 2, pt: 2, pb: 1 }}>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>רשימת כללים גלובליים</Typography>
        </Box>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 1, px: 2, pt: 2, pb: 1 }}>
          <TextField
            size="small"
            placeholder="חיפוש (כתובת, דומיין)..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(0); }}
            sx={{ minWidth: 220 }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" color="action" />
                </InputAdornment>
              ),
            }}
          />
          <FormControl size="small" sx={{ minWidth: 100 }}>
            <InputLabel>פעולה</InputLabel>
            <Select value={filterAction} label="פעולה" onChange={(e) => { setFilterAction(e.target.value); setPage(0); }}>
              <MenuItem value="">הכל</MenuItem>
              <MenuItem value="allow">אפשר</MenuItem>
              <MenuItem value="block">חסום</MenuItem>
            </Select>
          </FormControl>
        </Box>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell sortDirection={orderBy === 'url' ? order : false}>
                  <TableSortLabel active={orderBy === 'url'} direction={orderBy === 'url' ? order : 'asc'} onClick={() => { setOrderBy('url'); setOrder(orderBy === 'url' && order === 'asc' ? 'desc' : 'asc'); setPage(0); }}>
                    כתובת
                  </TableSortLabel>
                </TableCell>
                <TableCell sortDirection={orderBy === 'action' ? order : false}>
                  <TableSortLabel active={orderBy === 'action'} direction={orderBy === 'action' ? order : 'asc'} onClick={() => { setOrderBy('action'); setOrder(orderBy === 'action' && order === 'asc' ? 'desc' : 'asc'); setPage(0); }}>
                    פעולה
                  </TableSortLabel>
                </TableCell>
                <TableCell>תגיות</TableCell>
                <TableCell>סינון מלל</TableCell>
                <TableCell>סינון תמונות</TableCell>
                <TableCell>סינון קבצים</TableCell>
                <TableCell align="left">פעולות</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                <TableRow><TableCell colSpan={7}>טוען...</TableCell></TableRow>
              ) : filteredRules.length === 0 ? (
                <TableRow><TableCell colSpan={7}>{rules.length === 0 ? 'אין כללים גלובליים' : 'אין תוצאות לחיפוש או לסינון'}</TableCell></TableRow>
              ) : (
                paginatedRules.map((r) => (
                  <TableRow key={r.id} hover sx={{ '&:hover': { bgcolor: 'action.selected' } }}>
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
                      {ruleDisplayUrl(r)}
                    </TableCell>
                    <TableCell>{ACTION_LABELS[r.action] || r.action}</TableCell>
                    <TableCell>
                      {(r.tags || []).length ? (r.tags || []).map((t) => <Chip key={t} label={t} size="small" sx={{ mr: 0.5 }} />) : '—'}
                    </TableCell>
                    <TableCell>{r.action === 'block' ? '—' : (r.text_filter_enabled !== false ? 'כן' : 'לא')}</TableCell>
                    <TableCell>{r.action === 'block' ? '—' : (r.image_filter_enabled !== false ? 'כן' : 'לא')}</TableCell>
                    <TableCell>{r.action === 'block' ? '—' : (r.file_filter_enabled !== false ? 'כן' : 'לא')}</TableCell>
                    <TableCell align="left">
                      <IconButton size="small" onClick={() => openEdit(r)}><EditIcon /></IconButton>
                      <IconButton size="small" color="error" onClick={() => setDeleteConfirm(r.id)}><DeleteIcon /></IconButton>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
        {filteredRules.length > 0 && (
          <TablePagination
            component="div"
            count={filteredRules.length}
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
        <DialogTitle>{editingId ? 'עריכת כלל גלובלי' : 'הוספת כלל גלובלי'}</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            label="כתובת (דומיין/נתיב)"
            value={url}
            onChange={(e) => {
              const { cleaned, setSubdomains } = processUrlInput(e.target.value);
              setUrl(cleaned);
              setUrlError(validateDomainOrUrl(cleaned));
              if (setSubdomains) setIncludeSubdomains(true);
            }}
            placeholder="example.com או *.example.com/path"
            error={!!urlError}
            helperText={urlError || "פרוטוקול ו־*. יוסרו אוטומטית"}
            sx={{ mt: 1 }}
          />
          <FormControl fullWidth sx={{ mt: 2 }}>
            <InputLabel>פעולה</InputLabel>
            <Select value={action} label="פעולה" onChange={(e) => setAction(e.target.value as 'allow' | 'block')}>
              <MenuItem value="allow">אפשר</MenuItem>
              <MenuItem value="block">חסום</MenuItem>
            </Select>
          </FormControl>
          <FormControlLabel control={<Checkbox checked={includeSubdomains} onChange={(e) => setIncludeSubdomains(e.target.checked)} />} label="כלול תת-דומיינים" sx={{ mt: 2 }} />
          <Box sx={{ mt: 2 }}>
            <TagInput value={tags} onChange={setTags} label="תגיות" helperText="" />
          </Box>
          {action === 'allow' && (
            <Accordion sx={{ mt: 2 }} disableGutters elevation={0} square>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>הגדרות מתקדמות</AccordionSummary>
              <AccordionDetails>
                <FormControlLabel
                  control={<Checkbox checked={textFilterEnabled} onChange={(e) => setTextFilterEnabled(e.target.checked)} />}
                  label="סינון מלל לאתר"
                />
                <FormControlLabel
                  control={<Checkbox checked={imageFilterEnabled} onChange={(e) => setImageFilterEnabled(e.target.checked)} />}
                  label="סינון תמונות לאתר"
                  sx={{ display: 'block', mt: 0.5 }}
                />
                <FormControlLabel
                  control={<Checkbox checked={fileFilterEnabled} onChange={(e) => setFileFilterEnabled(e.target.checked)} />}
                  label="סינון קבצים לאתר (טרם נתמך)"
                  sx={{ display: 'block', mt: 0.5 }}
                />
              </AccordionDetails>
            </Accordion>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>ביטול</Button>
          <Button variant="contained" onClick={handleSave} disabled={saving || !url.trim() || !!urlError}>{editingId ? 'שמור' : 'הוסף'}</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={deleteConfirm !== null} onClose={() => setDeleteConfirm(null)}>
        <DialogTitle>מחיקת כלל גלובלי</DialogTitle>
        <DialogContent>האם למחוק את הכלל?</DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteConfirm(null)}>ביטול</Button>
          <Button color="error" variant="contained" onClick={() => deleteConfirm !== null && handleDelete(deleteConfirm)}>מחק</Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default AdminGlobalRulesPage;
